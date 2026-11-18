from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from random import Random
import sys
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from app import tts_engine as te


TEXT = "A" * 200 + "B" * 200 + "C" * 200
SAMPLES_PER_CHUNK = 4
STRIDE = SAMPLES_PER_CHUNK + 6000  # 0.25 seconds of silence at 24 kHz


@pytest.fixture
def torch_states(monkeypatch):
    """A small substitute for Torch's default CPU and CUDA generators in lightweight CI."""
    cpu, cuda = Random(81), Random(39)

    class Generator(Random):
        def manual_seed(self, seed):
            self.seed(seed)
            return self

        get_state = Random.getstate

    def manual_seed(seed):
        cpu.seed(seed)
        cuda.seed(seed)

    @contextmanager
    def fork_rng(devices):
        assert devices in ([], [0])
        generators = (cpu, cuda) if devices else (cpu,)
        snapshots = [g.getstate() for g in generators]
        try:
            yield
        finally:
            for g, snapshot in zip(generators, snapshots):
                g.setstate(snapshot)

    def get_cuda_state(device):
        assert device == 0
        return cuda.getstate()

    def set_cuda_state(state, device):
        assert device == 0
        cuda.setstate(state)

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        Generator=lambda device="cpu": Generator(),
        manual_seed=manual_seed,
        get_rng_state=cpu.getstate,
        set_rng_state=cpu.setstate,
        random=SimpleNamespace(fork_rng=fork_rng),
        cuda=SimpleNamespace(get_rng_state=get_cuda_state, set_rng_state=set_cuda_state),
    ))
    return cpu, cuda


def _draw(generator):
    return generator.randrange(500, 30000)


def _install_model(monkeypatch, tmp_path, torch_states, use_cuda=False):
    cpu, cuda = torch_states

    class Model:
        def generate_voice_clone(self, text, **kwargs):
            samples = [_draw(cpu), _draw(cpu)]
            samples += [_draw(cuda), _draw(cuda)] if use_cuda else [_draw(cpu), _draw(cpu)]
            if text == "fail":
                raise RuntimeError("inference failed")
            return [np.asarray(samples, dtype=np.float32) / 32768], 24000

    monkeypatch.setattr(te, "_cuda_available", lambda: use_cuda)
    monkeypatch.setattr(te, "_load", lambda *args: Model())
    monkeypatch.setattr(te.config, "OUTPUTS_DIR", tmp_path)


def _generate(progress_cb=None):
    wav = te.synthesize(TEXT, "english", "ref.wav", seed=123, model="0.6b", progress_cb=progress_cb)
    return sf.read(wav, dtype="int16")[0]


@pytest.mark.parametrize("pause_at", [0, 200])
@pytest.mark.parametrize("other_seed", [0, 456])
def test_fixed_seed_isolated_from_interleaved_cue(monkeypatch, tmp_path, torch_states,
                                                   pause_at, other_seed):
    _install_model(monkeypatch, tmp_path, torch_states)
    expected = _generate()
    paused, resume = Event(), Event()

    def progress(done, total):
        if done == pause_at:
            paused.set()
            assert resume.wait(5)

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(_generate, progress)
        try:
            assert paused.wait(5)
            other = pool.submit(te.synthesize_one, "another cue", "english", "ref.wav",
                                {"seed": other_seed, "model": "0.6b"})
            other.result(timeout=5)
        finally:
            resume.set()
        actual = first.result(timeout=5)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("use_cuda", [False, True])
def test_fixed_seed_advances_random_state_across_chunks(monkeypatch, tmp_path, torch_states, use_cuda):
    _install_model(monkeypatch, tmp_path, torch_states, use_cuda)
    ambient = [g.getstate() for g in torch_states]
    audio = _generate()

    ref_cpu = Random(123)
    ref_other = Random(123) if use_cuda else ref_cpu
    for i in range(3):
        expected = [_draw(ref_cpu), _draw(ref_cpu), _draw(ref_other), _draw(ref_other)]
        start = i * STRIDE
        np.testing.assert_array_equal(audio[start:start + SAMPLES_PER_CHUNK], expected)
    assert [g.getstate() for g in torch_states] == ambient


def test_fixed_seed_failure_restores_rng_and_unseeded_cues_keep_advancing(monkeypatch, tmp_path, torch_states):
    _install_model(monkeypatch, tmp_path, torch_states, use_cuda=True)
    ambient = [g.getstate() for g in torch_states]
    with pytest.raises(RuntimeError, match="inference failed"):
        te.synthesize_one("fail", "english", "ref.wav", {"seed": 123, "model": "0.6b"})
    assert [g.getstate() for g in torch_states] == ambient

    reference = [Random(), Random()]
    for rng, snapshot in zip(reference, ambient):
        rng.setstate(snapshot)
    for _ in range(2):
        audio, _ = te.synthesize_one("cue", "english", "ref.wav", {"seed": 0, "model": "0.6b"})
        expected = [_draw(rng) for rng in reference for _ in range(2)]
        np.testing.assert_array_equal(audio * 32768, expected)
