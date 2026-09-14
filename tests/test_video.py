import numpy as np
from basket.video import VideoWriter,read_frames,probe


def test_vfr_pts_survive_encode_decode(tmp_path):
    path=tmp_path/"variable.mp4"
    timestamps=[0,.033,.067,.13,.16,.23]
    with VideoWriter(path,96,64,30) as writer:
        for t in timestamps:
            writer.write(np.zeros((64,96,3),dtype=np.uint8),t)
    frames=list(read_frames(path))
    assert len(frames)==len(timestamps)
    assert all(abs(stamp["t"]-expected)<.001 for (stamp,_),expected in zip(frames,timestamps))
    assert all(stamp["timestamp_source"]=="pts" for stamp,_ in frames)
    metadata,_=probe(path)
    assert metadata["width"]==96
