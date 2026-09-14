"""Decode source PTS with PyAV; normalized playback keeps VFR timing."""
from fractions import Fraction
from pathlib import Path
import av


def read_frames(path):
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        base, previous = None, -1.0
        fps = float(stream.average_rate or 30)
        for index, frame in enumerate(container.decode(stream)):
            timestamp_source = "pts" if frame.pts is not None else "fps_fallback"
            original = float(frame.pts*frame.time_base) if frame.pts is not None else index/fps
            if base is None:
                base = original
            t = original-base
            if t <= previous:
                t = previous+1/fps
                timestamp_source = "monotonic_fallback"
            previous = t
            yield {"index": index, "t": round(t, 6), "pts": frame.pts,
                   "time_base": str(frame.time_base), "timestamp_source": timestamp_source}, frame.to_ndarray(format="bgr24")


def probe(path):
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError("動画ストリームがありません")
        stream = container.streams.video[0]
        duration = float(stream.duration*stream.time_base) if stream.duration else float(container.duration or 0)/1e6
        frame = next(container.decode(stream), None)
        if frame is None:
            raise ValueError("動画を読み込めません")
        if frame.width > 4096 or frame.height > 4096 or duration > 1200:
            raise ValueError("PoCでは4K以内・20分以内の動画を使ってください")
        rotation = float(frame.rotation) if hasattr(frame, "rotation") else 0
        if rotation % 360:
            raise ValueError("回転メタデータ付き動画です。横向きに書き出した動画を使用してください")
        return {"width": frame.width, "height": frame.height, "fps": float(stream.average_rate or 30),
                "duration_s": duration, "frame_count": stream.frames, "codec": stream.codec_context.name,
                "audio_in_source": bool(container.streams.audio)}, frame.to_ndarray(format="bgr24")


class VideoWriter:
    def __init__(self, path, width, height, fps=30):
        self.container = av.open(str(path), mode="w", options={"movflags": "+faststart"})
        self.stream = self.container.add_stream("libx264", rate=Fraction(fps).limit_denominator(1001))
        self.stream.width, self.stream.height = width, height
        self.stream.pix_fmt = "yuv420p"
        self.stream.time_base = Fraction(1, 90000)
        self.stream.codec_context.time_base = Fraction(1, 90000)
        self.stream.options = {"crf": "23", "preset": "veryfast"}
        self.previous_pts = -1

    def write(self, image, t):
        frame = av.VideoFrame.from_ndarray(image, format="bgr24")
        frame.pts = max(self.previous_pts+1, round(t*90000))
        self.previous_pts = frame.pts
        frame.time_base = Fraction(1, 90000)
        for packet in self.stream.encode(frame):
            self.container.mux(packet)

    def close(self):
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
