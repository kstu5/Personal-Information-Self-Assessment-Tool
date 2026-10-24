import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import kr.dogfoot.hwplib.reader.HWPReader;
import kr.dogfoot.hwplib.tool.textextractor.*;

// Read-only adapter. General HWP editing is deliberately not exposed.
public class HwpText {
  public static void main(String[] args) throws Exception {
    var file = HWPReader.fromFile(args[0]);
    var text = TextExtractor.extract(file, TextExtractMethod.InsertControlTextBetweenParagraphText);
    Files.writeString(Path.of(args[1]), text, StandardCharsets.UTF_8);
  }
}
