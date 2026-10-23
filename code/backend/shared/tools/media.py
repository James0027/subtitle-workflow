import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import FFMPEG_PATH, FFPROBE_PATH, MAX_PROCESS_DURATION_MS

class MediaError(Exception):
    pass

class MediaProbeError(MediaError):
    pass

class MediaDecodeError(MediaError):
    pass

class MediaDurationLimitError(MediaError):
    pass

class MediaTimeoutError(MediaError):
    pass


class MediaTool:
    def __init__(self, ffmpeg_path: str = FFMPEG_PATH, ffprobe_path: str = FFPROBE_PATH):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self._ffmpeg_version: Optional[str] = None
        self._ffprobe_version: Optional[str] = None

    def get_ffmpeg_version(self) -> str:
        if self._ffmpeg_version is None:
            try:
                res = subprocess.run(
                    [self.ffmpeg_path, "-version"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10,
                )
                if res.returncode == 0 and res.stdout:
                    first_line = res.stdout.strip().split("\n")[0]
                    self._ffmpeg_version = first_line
                else:
                    self._ffmpeg_version = "ffmpeg-unknown"
            except Exception:
                self._ffmpeg_version = "ffmpeg-unavailable"
        return self._ffmpeg_version

    def get_ffprobe_version(self) -> str:
        if self._ffprobe_version is None:
            try:
                res = subprocess.run(
                    [self.ffprobe_path, "-version"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10,
                )
                if res.returncode == 0 and res.stdout:
                    first_line = res.stdout.strip().split("\n")[0]
                    self._ffprobe_version = first_line
                else:
                    self._ffprobe_version = "ffprobe-unknown"
            except Exception:
                self._ffprobe_version = "ffprobe-unavailable"
        return self._ffprobe_version

    def probe(self, file_path: Path, timeout_sec: int = 30) -> Dict[str, Any]:
        """
        Runs ffprobe on the media file to obtain formats and streams metadata.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path),
        ]
        try:
            res = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=timeout_sec,
            )
            info = json.loads(res.stdout)
        except subprocess.TimeoutExpired:
            raise MediaTimeoutError(f"ffprobe timed out after {timeout_sec} seconds on {file_path.name}")
        except subprocess.CalledProcessError as e:
            raise MediaProbeError(f"ffprobe failed: {e.stderr or 'unknown error'}")
        except json.JSONDecodeError as e:
            raise MediaProbeError(f"Failed to parse ffprobe output: {e}")

        fmt = info.get("format", {})
        raw_dur_str = fmt.get("duration")
        if raw_dur_str is not None:
            try:
                raw_duration = float(raw_dur_str)
                duration_ms: Optional[int] = int(round(raw_duration * 1000))
            except (ValueError, TypeError):
                duration_ms = None
        else:
            duration_ms = None

        video_streams: List[Dict[str, Any]] = []
        audio_streams: List[Dict[str, Any]] = []
        subtitle_streams: List[Dict[str, Any]] = []

        for s in info.get("streams", []):
            codec_type = s.get("codec_type")
            stream_idx = s.get("index")
            codec_name = s.get("codec_name")
            tags = s.get("tags") or {}

            s_dur_str = s.get("duration")
            s_duration_ms: Optional[int] = None
            if s_dur_str is not None:
                try:
                    s_duration_ms = int(round(float(s_dur_str) * 1000))
                except (ValueError, TypeError):
                    s_duration_ms = duration_ms
            else:
                s_duration_ms = duration_ms

            if codec_type == "video":
                video_streams.append({
                    "stream_index": stream_idx,
                    "codec_name": codec_name,
                    "width": s.get("width"),
                    "height": s.get("height"),
                    "r_frame_rate": s.get("r_frame_rate"),
                    "avg_frame_rate": s.get("avg_frame_rate"),
                    "duration_ms": s_duration_ms,
                    "tags": tags,
                })
            elif codec_type == "audio":
                sr = s.get("sample_rate")
                sample_rate = int(sr) if sr and str(sr).isdigit() else None
                ch = s.get("channels")
                channels = int(ch) if ch is not None else None

                audio_streams.append({
                    "stream_index": stream_idx,
                    "codec_name": codec_name,
                    "sample_rate": sample_rate,
                    "channels": channels,
                    "channel_layout": s.get("channel_layout") or "",
                    "duration_ms": s_duration_ms,
                    "language": tags.get("language") or tags.get("LANGUAGE") or "und",
                    "title": tags.get("title") or "",
                    "tags": tags,
                })
            elif codec_type == "subtitle":
                subtitle_streams.append({
                    "stream_index": stream_idx,
                    "codec_name": codec_name,
                    "language": tags.get("language") or "und",
                    "title": tags.get("title") or "",
                    "tags": tags,
                })

        bit_rate_raw = fmt.get("bit_rate")
        bit_rate = int(bit_rate_raw) if bit_rate_raw and str(bit_rate_raw).isdigit() else None

        return {
            "duration_ms": duration_ms,
            "format_name": fmt.get("format_name", ""),
            "bit_rate": bit_rate,
            "video_streams": video_streams,
            "audio_streams": audio_streams,
            "subtitle_streams": subtitle_streams,
            "sound_present": len(audio_streams) > 0,
            "all_streams_count": len(info.get("streams", [])),
        }

    def decode_check(self, file_path: Path, timeout_sec: int = 60) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Runs full decode check using ffmpeg null-muxer across all streams (video and all audio tracks).
        Returns: (decode_ok, decode_error, coverage_info)
        """
        cmd = [
            self.ffmpeg_path,
            "-v", "error",
            "-i", str(file_path),
            "-map", "0:v?",
            "-f", "null",
            "-",
            "-map", "0:a?",
            "-f", "null",
            "-",
        ]
        try:
            res = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
            if res.returncode != 0:
                err = res.stderr.strip() or f"FFmpeg decode exit code {res.returncode}"
                return False, err, {"status": "failed", "all_tracks_checked": False}
            return True, None, {"status": "completed", "all_tracks_checked": True}
        except subprocess.TimeoutExpired:
            return False, f"FFmpeg decode timed out after {timeout_sec}s", {"status": "timeout", "all_tracks_checked": False}
        except Exception as e:
            return False, str(e), {"status": "error", "all_tracks_checked": False}

    def detect_volume(self, file_path: Path, stream_index: Optional[int] = None, timeout_sec: int = 30) -> Dict[str, Any]:
        """
        Runs volumedetect filter to detect digital silence and actual audio levels.
        Distinguishes 'audio track present' from 'usable sound present'.
        """
        map_arg = f"0:{stream_index}" if stream_index is not None else "0:a:0?"
        cmd = [
            self.ffmpeg_path,
            "-i", str(file_path),
            "-map", map_arg,
            "-af", "volumedetect",
            "-vn", "-sn", "-dn",
            "-f", "null",
            "-",
        ]
        try:
            res = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
            max_vol = None
            mean_vol = None
            for line in res.stderr.splitlines():
                if "max_volume:" in line:
                    parts = line.split("max_volume:")
                    val_str = parts[1].replace("dB", "").strip()
                    try:
                        max_vol = float(val_str)
                    except ValueError:
                        if "-inf" in val_str.lower():
                            max_vol = float("-inf")
                elif "mean_volume:" in line:
                    parts = line.split("mean_volume:")
                    val_str = parts[1].replace("dB", "").strip()
                    try:
                        mean_vol = float(val_str)
                    except ValueError:
                        if "-inf" in val_str.lower():
                            mean_vol = float("-inf")

            is_silent = (max_vol is not None and (max_vol == float("-inf") or max_vol < -85.0))
            return {
                "max_volume_db": max_vol,
                "mean_volume_db": mean_vol,
                "is_silent": is_silent,
                "usable": not is_silent if max_vol is not None else False,
            }
        except Exception as e:
            return {
                "max_volume_db": None,
                "mean_volume_db": None,
                "is_silent": False,
                "usable": False,
                "error": str(e),
            }

    def inspect_file(self, file_path: Path, max_duration_ms: int = MAX_PROCESS_DURATION_MS) -> Dict[str, Any]:
        """
        Performs probe, full decode check, and checks duration & audio usability.
        Rule: Original files exceeding 10 minutes are retained and inspected.
        Task confirmation will enforce the 10-minute processing limit without silent truncation.
        """
        try:
            probe_res = self.probe(file_path)
        except MediaError as e:
            return {
                "tool_version": self.get_ffmpeg_version(),
                "ffprobe_version": self.get_ffprobe_version(),
                "duration_ms": None,
                "channels": None,
                "sample_rate_hz": None,
                "codec": "unknown",
                "sound_present": False,
                "sound_usable": False,
                "is_silent": False,
                "measurement_status": "failed",
                "decode_ok": False,
                "decode_error": str(e),
                "decode_coverage": {"status": "failed", "all_tracks_checked": False},
                "video_streams": [],
                "audio_streams": [],
                "subtitle_streams": [],
            }

        duration_ms = probe_res.get("duration_ms")
        readable, decode_error, coverage = self.decode_check(file_path)

        primary_audio = probe_res["audio_streams"][0] if probe_res["audio_streams"] else None
        channels = primary_audio["channels"] if primary_audio else None
        sample_rate_hz = primary_audio["sample_rate"] if primary_audio else None
        codec = primary_audio["codec_name"] if primary_audio else (
            probe_res["video_streams"][0]["codec_name"] if probe_res["video_streams"] else "unknown"
        )

        vol_info = {"is_silent": False, "usable": False}
        if probe_res["sound_present"]:
            vol_info = self.detect_volume(file_path)

        inspection = {
            "tool_version": self.get_ffmpeg_version(),
            "ffprobe_version": self.get_ffprobe_version(),
            "duration_ms": duration_ms,
            "exceeds_task_limit": bool(duration_ms and duration_ms > max_duration_ms),
            "channels": channels,
            "sample_rate_hz": sample_rate_hz,
            "codec": codec,
            "sound_present": probe_res["sound_present"],
            "sound_usable": vol_info.get("usable", False) and not vol_info.get("is_silent", False),
            "is_silent": vol_info.get("is_silent", False),
            "volume_levels": vol_info,
            "measurement_status": "completed" if readable else "failed",
            "decode_ok": readable,
            "decode_error": decode_error,
            "decode_coverage": coverage,
            "video_streams": probe_res["video_streams"],
            "audio_streams": probe_res["audio_streams"],
            "subtitle_streams": probe_res["subtitle_streams"],
        }
        return inspection

    def extract_audio_track(
        self,
        video_path: Path,
        stream_index: int,
        output_wav_path: Path,
        timeout_sec: int = 60,
    ) -> Dict[str, Any]:
        """
        Extracts selected audio stream into lossless 16-bit PCM WAV.
        Validates that target stream_index is strictly an audio stream!
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        probe_res = self.probe(video_path)
        target_audio = next((s for s in probe_res["audio_streams"] if s["stream_index"] == stream_index), None)
        if not target_audio:
            # Check if this stream_index belongs to video
            is_video = any(s["stream_index"] == stream_index for s in probe_res["video_streams"])
            if is_video:
                raise MediaError(f"Stream index {stream_index} is a VIDEO stream, not an audio stream.")
            raise MediaError(f"Stream index {stream_index} not found among audio streams in {video_path.name}")

        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", str(video_path),
            "-map", f"0:{stream_index}",
            "-vn",
            "-c:a", "pcm_s16le",
            str(output_wav_path),
        ]
        try:
            res = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
            if res.returncode != 0:
                raise MediaDecodeError(f"Audio extraction failed: {res.stderr}")
        except subprocess.TimeoutExpired:
            raise MediaTimeoutError(f"Audio extraction timed out after {timeout_sec}s")

        if not output_wav_path.exists() or output_wav_path.stat().st_size == 0:
            raise MediaError("Extracted audio file is missing or empty")

        wav_probe = self.probe(output_wav_path)
        extracted_audio = wav_probe["audio_streams"][0] if wav_probe["audio_streams"] else {}
        vol_info = self.detect_volume(output_wav_path)
        return {
            "duration_ms": wav_probe.get("duration_ms"),
            "sample_rate_hz": extracted_audio.get("sample_rate"),
            "channels": extracted_audio.get("channels"),
            "codec": extracted_audio.get("codec_name", "pcm_s16le"),
            "source_stream_index": stream_index,
            "sound_usable": vol_info.get("usable", False) and not vol_info.get("is_silent", False),
            "is_silent": vol_info.get("is_silent", False),
            "volume_levels": vol_info,
            "tool_version": self.get_ffmpeg_version(),
        }

    def measure_audio_quality(self, file_path: Path, timeout_sec: int = 30) -> Dict[str, Any]:
        """
        Runs real FFmpeg astats and volumedetect on the audio file.
        Strict rule: Distinguish native measured statistics from uncalibrated / unmeasured indicators.
        Unmeasured SNR, P95 boundary error, and calibration scores are explicitly returned as None
        with clear explanatory statuses ("未测"). Never hardcode fake numbers or auto-advance based on uncalibrated scores.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        probe_res = self.probe(file_path, timeout_sec=timeout_sec)
        audio_stream = probe_res["audio_streams"][0] if probe_res["audio_streams"] else {}
        channels = audio_stream.get("channels")
        sample_rate_hz = audio_stream.get("sample_rate")

        vol_info = self.detect_volume(file_path, timeout_sec=timeout_sec)

        cmd = [
            self.ffmpeg_path,
            "-i", str(file_path),
            "-af", "astats",
            "-vn", "-sn", "-dn",
            "-f", "null",
            "-",
        ]
        peak_level_dbfs: Optional[float] = None
        rms_level_dbfs: Optional[float] = None
        flat_factor: Optional[float] = None
        dynamic_range: Optional[float] = None
        dc_offset: Optional[float] = None

        try:
            res = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
            # Parse Overall statistics or last channel
            for line in res.stderr.splitlines():
                line_str = line.strip()
                if "Peak level dB:" in line_str:
                    parts = line_str.split("Peak level dB:")
                    try:
                        peak_level_dbfs = float(parts[1].strip())
                    except Exception:
                        pass
                elif "RMS level dB:" in line_str:
                    parts = line_str.split("RMS level dB:")
                    try:
                        rms_level_dbfs = float(parts[1].strip())
                    except Exception:
                        pass
                elif "Flat factor:" in line_str:
                    parts = line_str.split("Flat factor:")
                    try:
                        flat_factor = float(parts[1].strip())
                    except Exception:
                        pass
                elif "Dynamic range:" in line_str:
                    parts = line_str.split("Dynamic range:")
                    try:
                        dynamic_range = float(parts[1].strip())
                    except Exception:
                        pass
                elif "DC offset:" in line_str:
                    parts = line_str.split("DC offset:")
                    try:
                        dc_offset = float(parts[1].strip())
                    except Exception:
                        pass
        except Exception:
            pass

        # Fallback to volumedetect max_volume if astats peak level wasn't parsed
        if peak_level_dbfs is None and vol_info.get("max_volume_db") is not None:
            peak_level_dbfs = vol_info["max_volume_db"]
        if rms_level_dbfs is None and vol_info.get("mean_volume_db") is not None:
            rms_level_dbfs = vol_info["mean_volume_db"]

        suspected_clipping = False
        if flat_factor is not None and flat_factor > 0.0:
            suspected_clipping = True
        elif peak_level_dbfs is not None and peak_level_dbfs >= -0.1:
            suspected_clipping = True

        is_silent = vol_info.get("is_silent", False)

        quality_risks: List[str] = []
        if is_silent:
            quality_risks.append("数字静音 / 极低电平警告")
        if suspected_clipping:
            quality_risks.append("疑似音频削波失真 (Peak >= -0.1 dBFS 或 Flat factor > 0)")
        if rms_level_dbfs is not None and rms_level_dbfs < -40.0 and not is_silent:
            quality_risks.append("音频平均响度过低 (RMS < -40 dBFS)")

        return {
            "channels": channels,
            "sample_rate_hz": sample_rate_hz,
            "duration_ms": probe_res.get("duration_ms"),
            "peak_level_dbfs": peak_level_dbfs,
            "rms_level_dbfs": rms_level_dbfs,
            "flat_factor": flat_factor,
            "dc_offset": dc_offset,
            "dynamic_range_db": dynamic_range,
            "suspected_clipping": suspected_clipping,
            "is_silent": is_silent,
            "usable": not is_silent and bool(audio_stream),
            "quality_risks": quality_risks,
            # Explicitly unmeasured fields per contract and user instruction
            "snr_db": None,
            "snr_status": "未测 (缺少纯净语音对照与算法校准)",
            "p95_boundary_error_ms": None,
            "p95_status": "未测 (需人工参考标注校准)",
            "calibrated_confidence": None,
            "calibration_status": "未测 (模型自评未校准，不能作为准确率依据)",
        }

    def slice_audio_fixed(
        self,
        audio_path: Path,
        output_dir: Path,
        slice_duration_sec: float = 10.0,
        start_ms: int = 0,
        end_ms: Optional[int] = None,
        master_offset_ms: Optional[int] = None,
        chunk_id_prefix: str = "chunk",
        start_chunk_idx: int = 0,
        timeout_sec: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Slices audio file into fixed 10-second chunks, preserving the exact real duration of the tail slice.
        Computes accurate master timeline offset, real SHA-256 hash, and audio quality measurements for each slice.
        Supports Task/run-isolated chunk_id generation and non-zero master offset mapping without double-slicing.
        """
        import hashlib

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        probe_res = self.probe(audio_path, timeout_sec=timeout_sec)
        total_audio_ms = probe_res.get("duration_ms") or 0
        if end_ms is None or end_ms > total_audio_ms or end_ms <= 0:
            end_ms = total_audio_ms

        if start_ms >= end_ms:
            raise MediaError(f"切片起点 ({start_ms}ms) 必须小于终点 ({end_ms}ms)")

        # If master_offset_ms is not provided, default to start_ms
        if master_offset_ms is None:
            master_offset_ms = start_ms

        output_dir.mkdir(parents=True, exist_ok=True)
        slice_step_ms = int(round(slice_duration_sec * 1000))
        chunks: List[Dict[str, Any]] = []

        curr_ms = start_ms
        chunk_idx = start_chunk_idx

        while curr_ms < end_ms:
            chunk_end_ms = min(curr_ms + slice_step_ms, end_ms)
            # A sub-250ms residual stays attached to its preceding real audio, never dropped.
            if 0 < end_ms - chunk_end_ms < 250:
                chunk_end_ms = end_ms
            chunk_duration_ms = chunk_end_ms - curr_ms

            # Master timeline mapping: master_offset_ms represents master timestamp at start_ms
            local_rel_ms = curr_ms - start_ms
            chunk_master_start_ms = master_offset_ms + local_rel_ms
            chunk_master_end_ms = chunk_master_start_ms + chunk_duration_ms

            chunk_id = f"{chunk_id_prefix}_{chunk_idx:03d}"
            chunk_file = output_dir / f"{chunk_id}.wav"

            start_sec = curr_ms / 1000.0
            dur_sec = chunk_duration_ms / 1000.0

            cmd = [
                self.ffmpeg_path,
                "-y",
                "-ss", f"{start_sec:.3f}",
                "-t", f"{dur_sec:.3f}",
                "-i", str(audio_path),
                "-c:a", "pcm_s16le",
                str(chunk_file),
            ]
            res = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
            )
            if res.returncode != 0 or not chunk_file.exists():
                raise MediaDecodeError(f"切片生成失败 ({chunk_id}): {res.stderr}")

            # Compute SHA-256 of slice
            hasher = hashlib.sha256()
            with open(chunk_file, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            sha256 = hasher.hexdigest()

            # Measure audio quality on slice
            quality = self.measure_audio_quality(chunk_file, timeout_sec=timeout_sec)

            chunks.append({
                "chunk_id": chunk_id,
                "chunk_index": chunk_idx,
                "start_ms": chunk_master_start_ms,
                "end_ms": chunk_master_end_ms,
                "offset_ms": chunk_master_start_ms,
                "duration_ms": chunk_duration_ms,
                "checksum_sha256": sha256,
                "file_path": str(chunk_file),
                "quality_stats": quality,
                "status": "sliced",
            })

            curr_ms = chunk_end_ms
            chunk_idx += 1

        return chunks


media_tool = MediaTool()
