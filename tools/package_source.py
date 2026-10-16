from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
destination=ROOT/"exports"/"Hilykan_Shoe_QC_Simulator_Source.zip"
folders=["gui","cad_import","cad_manifest","scene3d","motion","controllers","sensors","state_machine","simulation","qc",
         "collision","export","config","logs","tests","tools","cache","reports","Shoe_QC_Dual_Shutter_STEP_CAD_BOM_RevA"]
files=[ROOT/n for n in ("main.py","README.md","requirements.txt","requirements-lock.txt","pytest.ini","launch.bat","setup.bat",".gitignore")]
for folder in folders:
    files.extend(p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix!=".pyc"
                 and (folder!="logs" or p.suffix==".py") and p.name!="user.json" and not p.name.startswith("~$")
                 and (folder!="Shoe_QC_Dual_Shutter_STEP_CAD_BOM_RevA" or p.suffix.lower() in (".step",".stp",".sldasm",".json",".csv",".py",".txt")))
files.extend(p for p in (ROOT/"exports").glob("Hilykan_QC_Alternating_1080p.*") if "partial" not in p.name)
files.extend(p for p in (ROOT/"exports").glob("Hilykan_Multiface_QC_720p.*") if "partial" not in p.name)
files.extend(p for p in (ROOT/"exports"/"qc_captures").glob("*") if p.suffix in (".png",".json"))
destination.parent.mkdir(exist_ok=True)
temporary=destination.with_name(destination.stem+".partial.zip")
with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for path in sorted(set(files)):
        archive.write(path,path.relative_to(ROOT))
with zipfile.ZipFile(temporary) as archive:
    if archive.testzip():
        raise RuntimeError("Source ZIP verification failed")
    count=len(archive.namelist())
temporary.replace(destination)
print("Packaged",count,"files; bytes",destination.stat().st_size)
