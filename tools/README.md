# Generátor xenon_police (LSPD MLO)

Celé MLO vzniká z kódu: dispozice → geometrie a kolize → CodeWalker XML → binární soubory pro FiveM.

```
tools/
├── generator/
│   ├── layout.py      # půdorysy: místnosti, dveře, okna, zóny + validace průchodnosti
│   ├── building.py    # stěny z půdorysu, otvory, sklo, podlahy, stropy, světla, schodiště, fasáda, areál
│   ├── furnish.py     # vybavení místností (vlastní geometrie + vanilla propy), cedule
│   ├── textures.py    # procedurální textury (PNG → DDS DXT1/DXT5 s mipmapami)
│   ├── materials.py   # materiály: shader, textury, mapování UV, kolizní materiál
│   ├── mesh.py        # mesh a kolizní buildery
│   ├── cwxml.py       # zápis CodeWalker XML (ydr, ybn, ytd, ytyp, ymap)
│   ├── plans.py       # obrázky půdorysů
│   ├── preview.py     # softwarový renderer náhledů (QA)
│   ├── build.py       # celý build
│   └── config.json    # umístění ve světě
└── cwconv/            # konzolový převodník XML → binárka nad CodeWalker.Core
```

## Požadavky

- Python 3.10+ s `numpy` a `Pillow`
- ImageMagick (`convert`) s podporou DDS
- .NET SDK 8
- Zdrojáky CodeWalkeru (jen knihovna CodeWalker.Core, je `netstandard2.0` – funguje na Windows i Linuxu)

## Build

```bash
# jednorázově: CodeWalker + převodník
git clone https://github.com/dexyfex/CodeWalker _deps/CodeWalker
dotnet build tools/cwconv -c Release

# přestavba resource (z kořene repozitáře)
cd tools/generator
python3 build.py --out ../../xenon_police --cwconv ../cwconv/bin/Release/net8.0/cwconv.dll
```

Volitelně `--objectlist cesta/ObjectList.ini` (z DurtyFree/gta-v-data-dumps) ověří, že všechny vanilla modely existují.

## Přesun stanice

V `config.json` nastav `origin` = `[X, Y, Z]` jihozápadního rohu budovy (Z = výška terénu + 0,35 m)
a spusť build. Hlavní vchod je na jižní straně, 28 m od rohu na ose X.

## Náhledy

```bash
python3 preview.py ../../_build/xml/xenon_police_txd out_dir aerial front lobby dispatch plans
python3 plans.py out_dir
```
