import pytest

from src.features.ffmpeg_env import system_has_ffmpeg_shared_libs_for_torchcodec


@pytest.mark.skipif(
    not system_has_ffmpeg_shared_libs_for_torchcodec(),
    reason="시스템에 FFmpeg shared libs(예: libavutil) 없음. macOS: brew install ffmpeg",
)
def test_torchaudio_save_writes_minimal_wav(tmp_path):
    """torchaudio.save는 Demucs가 스템을 쓸 때 쓰인다. TorchCodec/FFmpeg 없으면 스킵."""
    import torch
    import torchaudio

    path = tmp_path / "t.wav"
    wave = torch.zeros(1, 100)
    torchaudio.save(str(path), wave, sample_rate=16_000)
    assert path.is_file()
    assert path.stat().st_size > 0
