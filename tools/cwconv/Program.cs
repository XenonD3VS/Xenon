using System;
using System.IO;
using System.Xml;
using CodeWalker.GameFiles;

class P {
  static MetaFormat Fmt(string f){
    f=f.ToLowerInvariant();
    if(f.EndsWith(".ydr.xml"))return MetaFormat.Ydr;
    if(f.EndsWith(".ybn.xml"))return MetaFormat.Ybn;
    if(f.EndsWith(".ytd.xml"))return MetaFormat.Ytd;
    if(f.EndsWith(".ymap.xml")||f.EndsWith(".ytyp.xml"))return MetaFormat.RSC;
    throw new Exception("unknown "+f);
  }
  static int Main(string[] a){
    try{
      if(a[0]=="build"){ // build in.xml out
        var doc=new XmlDocument(); doc.Load(a[1]);
        var tex=a.Length>3?a[3]:Path.GetDirectoryName(Path.GetFullPath(a[1]));
        var data=XmlMeta.GetData(doc,Fmt(a[1]),tex);
        if(data==null){Console.Error.WriteLine("FAILED "+a[1]);return 2;}
        File.WriteAllBytes(a[2],data); Console.WriteLine($"built {a[2]} {data.Length} bytes"); return 0;
      }
      if(a[0]=="dump"){ // dump bin outdir
        var data=File.ReadAllBytes(a[1]);
        var e=RpfFile.CreateResourceFileEntry(ref data,0);
        e.Name=Path.GetFileName(a[1]); e.NameLower=e.Name.ToLowerInvariant();
        data=ResourceBuilder.Decompress(data);
        string fn; var xml=MetaXml.GetXml(e,data,out fn,a[2]);
        if(string.IsNullOrEmpty(xml)){Console.Error.WriteLine("DUMP FAILED");return 3;}
        Directory.CreateDirectory(a[2]);
        File.WriteAllText(Path.Combine(a[2],fn),xml); Console.WriteLine("dumped "+fn+" "+xml.Length); return 0;
      }
    }catch(Exception ex){Console.Error.WriteLine(ex.ToString());return 1;}
    return 9;
  }
}
