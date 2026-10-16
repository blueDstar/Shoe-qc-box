import sys
from pathlib import Path
import json
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

path=ROOT/"exports"/"Hilykan_QC_Alternating_1080p.mp4"
trace=[json.loads(s) for s in path.with_suffix(".frames.jsonl").read_text(encoding="utf-8").splitlines()]
video=cv2.VideoCapture(str(path))
for name,index in (("video_closed",0),("video_left_inspect",240),("video_right_inspect",720),("video_completed",996)):
    video.set(cv2.CAP_PROP_POS_FRAMES,index)
    okay,frame=video.read()
    if not okay:
        raise RuntimeError("Unable to decode frame "+str(index))
    cv2.imwrite(str(ROOT/"reports"/(name+".png")),frame)
video.release()
print(json.dumps({"bytes":path.stat().st_size,"frames":len(trace),"final":trace[-1],
                  "states":list(dict.fromkeys(f["state"] for f in trace))}))
