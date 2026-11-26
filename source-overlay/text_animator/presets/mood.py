"""Six polished mood presets: two energetic, two calm and two melancholic."""
from __future__ import annotations
from math import pi, sin
from moviepy import CompositeVideoClip
from moviepy.video.fx import Resize
from .base import AnimationPreset, RenderContext, make_background
from ..effects import make_styled_text_clip, apply_fade, ease_out_cubic, ease_out_back


class _MoodPreset(AnimationPreset):
    motion = ""
    def build(self, ctx: RenderContext):
        n = len(ctx.words)
        total = max(1.0, n * (ctx.word_duration + ctx.gap) - ctx.gap + ctx.end_hold)
        clips = [make_background(ctx, total)]
        width, height = ctx.size
        for i, word in enumerate(ctx.words):
            self._check_cancel(ctx)
            self._progress(ctx, i + 1, n, f"{self.name}: {word}")
            start = i * (ctx.word_duration + ctx.gap)
            enter = max(0.12, min(ctx.word_duration * 0.42, 0.72))
            txt = make_styled_text_clip(word, ctx.font_path, ctx.font_size, ctx.text_color,
                ctx.word_duration, ctx.outline, ctx.outline_width, ctx.shadow, ctx.shadow_offset)
            tw, th = txt.size
            if self.motion == "impact":
                def scale(t, d=enter):
                    return max(0.65, 0.12 + 0.88 * ease_out_back(min(1.0, max(0.0, t / d)), 1.9))
                txt = txt.with_effects([Resize(scale)])
                def pos(t, w=tw, h=th):
                    p = min(1.0, max(0.0, t / enter))
                    return ((width-w)/2 + (1-p)*sin(t*62)*10, (height-h)/2)
                txt = txt.with_position(pos)
                txt = apply_fade(txt, fade_in=0.035, fade_out=0.16)
            elif self.motion == "rush":
                def pos(t, w=tw, h=th, direction=(-1 if i % 2 == 0 else 1)):
                    p = ease_out_cubic(min(1.0, max(0.0, t / enter)))
                    x0 = -w-24 if direction < 0 else width+24
                    return (x0 + ((width-w)/2-x0)*p, (height-h)/2)
                txt = txt.with_position(pos)
                txt = apply_fade(txt, fade_in=0.08, fade_out=0.18)
            elif self.motion == "flow":
                def pos(t, w=tw, h=th):
                    p = ease_out_cubic(min(1.0, max(0.0, t / enter)))
                    return ((width-w)/2, (height-h)/2 + (1-p)*34 + sin(t*1.15)*8)
                txt = txt.with_position(pos)
                txt = txt.with_effects([Resize(lambda t: 0.94 + 0.06*ease_out_cubic(min(1.0,t/enter)))])
                txt = apply_fade(txt, fade_in=min(0.55,enter), fade_out=0.38)
            elif self.motion == "serenity":
                def pos(t, w=tw, h=th):
                    return ((width-w)/2, (height-h)/2 + sin(t/max(ctx.word_duration,0.1)*pi)*12)
                txt = txt.with_position(pos)
                txt = txt.with_effects([Resize(lambda t: 0.985 + 0.015*sin(min(1.0,t/max(ctx.word_duration,0.1))*pi))])
                txt = apply_fade(txt, fade_in=min(0.75,ctx.word_duration*0.38), fade_out=0.55)
            elif self.motion == "melancholy":
                def pos(t, w=tw, h=th):
                    p = min(1.0,max(0.0,t/enter))
                    return ((width-w)/2,(height-h)/2+(1-ease_out_cubic(p))*22+p*9)
                txt = txt.with_position(pos)
                txt = apply_fade(txt, fade_in=min(0.8,ctx.word_duration*0.48), fade_out=0.5)
            else:  # rainy memories
                def pos(t, w=tw, h=th, idx=i):
                    p = min(1.0,max(0.0,t/enter))
                    return ((width-w)/2,(height-h)/2+(1-ease_out_cubic(p))*16+sin(t*0.7+idx*0.4)*5)
                txt = txt.with_position(pos)
                txt = txt.with_effects([Resize(lambda t: 1.04-0.04*ease_out_cubic(min(1.0,t/enter)))])
                txt = apply_fade(txt, fade_in=min(0.9,ctx.word_duration*0.5), fade_out=0.65)
            clips.append(txt.with_start(start).with_duration(ctx.word_duration))
        return CompositeVideoClip(clips, size=ctx.size).with_fps(ctx.fps), total


class ImpactStrikePreset(_MoodPreset):
    name, description, motion = "impact_strike", "Action · Impact Strike — explosive scale impact and micro-shake", "impact"
class CinematicRushPreset(_MoodPreset):
    name, description, motion = "cinematic_rush", "Action · Cinematic Rush — fast directional movement", "rush"
class SoftFlowPreset(_MoodPreset):
    name, description, motion = "soft_flow", "Calm · Soft Flow — gentle rise and floating drift", "flow"
class SerenityPreset(_MoodPreset):
    name, description, motion = "serenity", "Calm · Serenity — breathing scale and graceful drift", "serenity"
class MelancholyFadePreset(_MoodPreset):
    name, description, motion = "melancholy_fade", "Sad · Melancholy Fade — lingering fade and downward drift", "melancholy"
class RainyMemoriesPreset(_MoodPreset):
    name, description, motion = "rainy_memories", "Sad · Rainy Memories — hazy reveal and delicate drift", "rainy"
