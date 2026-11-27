from types import SimpleNamespace
from text_animator.batch_ui import _payload

class Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value

def _base():
    return {
        "preset_name":"classic", "font_name_or_path":"Noto Sans", "font_size":90,
        "color_mode":"white_on_black", "word_duration":0.85, "gap":0.08, "end_hold":1.2,
        "outline":False, "shadow":False, "outline_width":3, "shadow_offset":4,
        "auto_fit_font":True, "transition":"fade", "transition_duration":0.25,
        "audio_volume":0.85, "audio_fade_in":0.15, "audio_fade_out":0.25,
        "bg_image_path":None, "hardware_backend":"auto", "size":(1280,720),
    }

def test_batch_preview_payload_applies_csv_overrides(tmp_path):
    csv=tmp_path/"items.csv"; csv.write_text("title,sentence\n",encoding="utf-8")
    app=SimpleNamespace(_gather_batch_params=_base,csv_entry=Var(str(csv)),batch_fixed_audio_var=Var(""))
    p=_payload(app,{"preset":"typewriter","font_size":"72","color_mode":"black_on_white",
                    "word_duration":"0.6","outline":"yes","transition":"zoom","resolution":"1080x1920"})
    assert p["preset_name"]=="typewriter" and p["font_size"]==72
    assert p["color_mode"]=="black_on_white" and p["word_duration"]==0.6
    assert p["outline"] is True and p["transition"]=="zoom" and p["size"]==(1080,1920)
    assert p["audio_path"] is None

def test_batch_preview_resolves_relative_audio_and_explicit_silence(tmp_path):
    csv=tmp_path/"items.csv"; folder=tmp_path/"audio"; folder.mkdir()
    track=folder/"music.mp3"; track.write_bytes(b"fake")
    app=SimpleNamespace(_gather_batch_params=_base,csv_entry=Var(str(csv)),batch_fixed_audio_var=Var(""))
    assert _payload(app,{"audio":"audio/music.mp3"})["audio_path"]==str(track.resolve())
    assert _payload(app,{"audio":"none"})["audio_path"] is None
