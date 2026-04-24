def test_check_hardware_resolves_mps_when_only_mps_available(monkeypatch):
    """CUDA가 없고 MPS만 있으면 demucs_device는 mps여야 한다."""
    monkeypatch.setattr("src.features.system.torch.cuda.is_available", lambda: False)
    monkeypatch.setattr(
        "src.features.system.torch.backends.mps.is_available", lambda: True
    )

    from src.features.system import check_hardware_compatibility

    stats = check_hardware_compatibility()
    assert stats["demucs_device"] == "mps"
