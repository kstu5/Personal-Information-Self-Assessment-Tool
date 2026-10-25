import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.List;
import kr.dogfoot.hwplib.tool.blankfilemaker.BlankFileMaker;
import kr.dogfoot.hwplib.reader.HWPReader;
import kr.dogfoot.hwplib.writer.HWPWriter;
import kr.dogfoot.hwplib.object.bodytext.paragraph.Paragraph;
import kr.dogfoot.hwplib.tool.textextractor.*;

/** Build a real HWP 5 binary from synthetic text, then read it back. */
public class CreateFormatHwp {
  public static void main(String[] args) throws Exception {
    List<String> lines = Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8);
    var hwp = BlankFileMaker.make();
    var info = hwp.getDocInfo();
    for (var list : List.of(info.getHangulFaceNameList(), info.getEnglishFaceNameList(),
        info.getHanjaFaceNameList(), info.getJapaneseFaceNameList(), info.getEtcFaceNameList(),
        info.getSymbolFaceNameList(), info.getUserFaceNameList())) {
      for (var font : list) font.setName("맑은 고딕");
    }
    for (var shape : info.getCharShapeList()) shape.setBaseSize(1100);
    var title = info.getCharShapeList().get(0).clone();
    title.setBaseSize(1800);
    int titleId = info.getCharShapeList().size();
    info.getCharShapeList().add(title);
    var section = hwp.getBodyText().getSectionList().get(0);
    var first = section.getParagraph(0);
    // Preserve the section/column controls in the first paragraph only.
    var template = first.clone();
    template.getControlList().clear();
    template.createText();
    template.getText().addNewCharControlChar().setCode("\r");
    for (int i=0; i<lines.size(); i++) {
      Paragraph p;
      if (i==0) {
        p=first;
        var chars=p.getText().getCharList();
        chars.remove(chars.size()-1);
      } else {
        p=template.clone();
        p.createText();
        section.insertParagraph(i,p);
      }
      p.getText().addString(lines.get(i));
      p.getText().addNewCharControlChar().setCode("\r");
      p.getCharShape().getPositonShapeIdPairList().clear();
      p.getCharShape().addParaCharShape(0,i==0?titleId:0);
      p.getHeader().setLastInList(i==lines.size()-1);
      if (p.getLineSeg()!=null) {
        for (var seg:p.getLineSeg().getLineSegItemList()) {
          seg.setLineVerticalPosition(i*1800);
          seg.setLineHeight(i==0?1800:1100);
          seg.setTextPartHeight(i==0?1800:1100);
          seg.setDistanceBaseLineToLineVerticalPosition(i==0?1530:935);
          seg.setLineSpace(600);
        }
      }
    }
    HWPWriter.toFile(hwp,args[1]);
    String readback=TextExtractor.extract(HWPReader.fromFile(args[1]),TextExtractMethod.InsertControlTextBetweenParagraphText);
    for (String line:lines) if (!line.isBlank() && !readback.contains(line))
      throw new IllegalStateException("HWP readback mismatch");
    Files.writeString(Path.of(args[2]),readback,StandardCharsets.UTF_8);
    System.out.println("HWP binary written and all lines read back");
  }
}
