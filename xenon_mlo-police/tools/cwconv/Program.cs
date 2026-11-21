// cwconv - tiny command line wrapper around CodeWalker.Core
// Converts CodeWalker XML files (.ydr.xml, .ybn.xml, .ytyp.xml, .ymap.xml) to binary GTA V files.
//
//   cwconv <input folder with *.xml + *.dds> <output folder>
//
using System;
using System.IO;
using System.Xml;
using CodeWalker.GameFiles;

class Program
{
    static int Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.WriteLine("usage: cwconv <xml folder> <output folder>");
            return 1;
        }
        var input = Path.GetFullPath(args[0]);
        var output = Path.GetFullPath(args[1]);
        Directory.CreateDirectory(output);

        int failed = 0;
        foreach (var path in Directory.GetFiles(input, "*.xml"))
        {
            var name = Path.GetFileName(path);
            name = name.Substring(0, name.Length - 4); // strip .xml
            try
            {
                var doc = new XmlDocument();
                doc.Load(path);
                var fmt = XmlMeta.GetXMLFormat(name.ToLowerInvariant(), out int _);
                var data = XmlMeta.GetData(doc, fmt, input); // DDS textures are read from the input folder
                if (data == null) throw new Exception("conversion returned no data");
                File.WriteAllBytes(Path.Combine(output, name), data);
                Console.WriteLine($"  {name,-40} {data.Length,10} B  ({fmt})");
            }
            catch (Exception ex)
            {
                failed++;
                Console.WriteLine($"  FAILED {name}: {ex.Message}");
            }
        }
        return failed == 0 ? 0 : 2;
    }
}
