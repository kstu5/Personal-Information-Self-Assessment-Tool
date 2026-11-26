import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import kr.dogfoot.hwplib.reader.HWPReader;
import kr.dogfoot.hwplib.tool.textextractor.*;
import kr.dogfoot.hwplib.org.apache.poi.poifs.filesystem.*;
import kr.dogfoot.hwplib.org.apache.poi.hpsf.ClassID;
import java.io.*;
import java.util.*;

// Fresh compound-file IO. HWP records and verified edit positions are handled
// by the Python adapter; no in-place writes or old allocation sectors survive.
public class HwpText {
  private static final byte[] MAGIC="HWPSTRM1".getBytes(StandardCharsets.US_ASCII);
  private static final int LIMIT=80*1024*1024;
  private static class Item {
    int kind; String path; byte[] data;
    Item(int kind,String path,byte[] data){this.kind=kind;this.path=path;this.data=data;}
  }
  private static void collect(DirectoryEntry directory,String path,List<Item> items,long[] total) throws Exception {
    byte[] clsid=new byte[16];directory.getStorageClsid().write(clsid,0);
    items.add(new Item(0,path,clsid));
    for(Iterator<Entry> it=directory.getEntries();it.hasNext();){
      Entry entry=it.next();String name=entry.getName();
      if(name.indexOf('/')>=0||name.indexOf('\\')>=0||name.equals(".")||name.equals(".."))throw new IOException("Invalid stream name");
      String child=path.isEmpty()?name:path+"/"+name;
      if(entry.isDirectoryEntry())collect((DirectoryEntry)entry,child,items,total);
      else{
        DocumentEntry document=(DocumentEntry)entry;
        if(document.getSize()<0||(total[0]+=document.getSize())>LIMIT)throw new IOException("Stream limit");
        try(InputStream in=new DocumentInputStream(document)){
          byte[] bytes=in.readNBytes(document.getSize());if(bytes.length!=document.getSize())throw new IOException("Truncated stream");
          items.add(new Item(1,child,bytes));
        }
      }
      if(items.size()>4000)throw new IOException("Entry limit");
    }
  }
  private static void unpack(Path source,Path output) throws Exception {
    List<Item> items=new ArrayList<>();
    try(InputStream in=Files.newInputStream(source)){
      POIFSFileSystem fs=new POIFSFileSystem(in);collect(fs.getRoot(),"",items,new long[]{0});
    }
    try(DataOutputStream out=new DataOutputStream(Files.newOutputStream(output))){
      out.write(MAGIC);out.writeInt(items.size());
      for(Item item:items){byte[] path=item.path.getBytes(StandardCharsets.UTF_8);out.writeByte(item.kind);out.writeInt(path.length);out.write(path);out.writeInt(item.data.length);out.write(item.data);}
    }
  }
  private static void pack(Path source,Path output) throws Exception {
    POIFSFileSystem fs=new POIFSFileSystem();Map<String,DirectoryEntry> directories=new HashMap<>();directories.put("",fs.getRoot());
    long total=0;
    try(DataInputStream in=new DataInputStream(Files.newInputStream(source))){
      if(!Arrays.equals(in.readNBytes(8),MAGIC))throw new IOException("Invalid package");
      int count=in.readInt();if(count<1||count>4000)throw new IOException("Entry limit");
      Set<String> seen=new HashSet<>();
      for(int i=0;i<count;i++){
        int kind=in.readUnsignedByte(),size=in.readInt();if(size<0||size>4096)throw new IOException("Path limit");
        String path=new String(in.readNBytes(size),StandardCharsets.UTF_8);
        if(!seen.add(path)||path.startsWith("/")||path.indexOf('\\')>=0)throw new IOException("Invalid path");
        int length=in.readInt();if(length<0||(total+=length)>LIMIT)throw new IOException("Stream limit");
        byte[] bytes=in.readNBytes(length);if(bytes.length!=length)throw new IOException("Truncated stream");
        int slash=path.lastIndexOf('/');String parent=slash<0?"":path.substring(0,slash),name=slash<0?path:path.substring(slash+1);
        if(kind==0){
          if(bytes.length!=16)throw new IOException("Invalid directory");
          DirectoryEntry directory=path.isEmpty()?fs.getRoot():directories.get(parent).createDirectory(name);
          directory.setStorageClsid(new ClassID(bytes,0));directories.put(path,directory);
        }else if(kind==1&&!name.isEmpty()&&directories.containsKey(parent))directories.get(parent).createDocument(name,new ByteArrayInputStream(bytes));
        else throw new IOException("Invalid entry");
      }
      if(in.read()!=-1)throw new IOException("Trailing data");
    }
    try(OutputStream out=Files.newOutputStream(output)){fs.writeFilesystem(out);}
  }
  public static void main(String[] args) throws Exception {
    if(args.length==3){
      if(args[0].equals("unpack"))unpack(Path.of(args[1]),Path.of(args[2]));
      else if(args[0].equals("pack"))pack(Path.of(args[1]),Path.of(args[2]));
      else throw new IOException("Unknown operation");
      return;
    }
    var file = HWPReader.fromFile(args[0]);
    var text = TextExtractor.extract(file, TextExtractMethod.InsertControlTextBetweenParagraphText);
    Files.writeString(Path.of(args[1]), text, StandardCharsets.UTF_8);
  }
}
