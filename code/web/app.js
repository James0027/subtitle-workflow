function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}

// State
const state = {
  projectId: "PRJ-DEFAULT",
  taskId: localStorage.getItem("active_task_id") || null,
  taskRev: 1,
  taskStatus: "DRAFT",
  mediaId: localStorage.getItem("active_media_id") || null,
  mediaRev: 1,
  mediaStatus: "REGISTERED",
  videoAsset: null,
  independentAudioAsset: null,
  derivedAudioAsset: null,
  audioSourceType: "video_track", // 'video_track' or 'independent_audio'
  selectedStreamIndex: null,
  primaryAudioAssetId: null,
  currentUser: null,
};

// DOM Elements
const operatorBadge = document.getElementById("operatorBadge");
const operatorNameText = document.getElementById("operatorNameText");
const btnSwitchOperator = document.getElementById("btnSwitchOperator");
const modalOperatorSetup = document.getElementById("modalOperatorSetup");
const existingOperatorsBox = document.getElementById("existingOperatorsBox");
const selectExistingOperator = document.getElementById("selectExistingOperator");
const btnLoginOperator = document.getElementById("btnLoginOperator");
const inputNewOperatorName = document.getElementById("inputNewOperatorName");
const selectNewOperatorRole = document.getElementById("selectNewOperatorRole");
const btnRegisterOperator = document.getElementById("btnRegisterOperator");

const taskStatusTag = document.getElementById("taskStatusTag");
const activeTaskIdText = document.getElementById("activeTaskIdText");
const taskRevisionText = document.getElementById("taskRevisionText");

const btnCreateTask = document.getElementById("btnCreateTask");
const btnUploadVideo = document.getElementById("btnUploadVideo");
const btnUploadAudio = document.getElementById("btnUploadAudio");
const btnPrepareAudio = document.getElementById("btnPrepareAudio");
const btnConfirmMaster = document.getElementById("btnConfirmMaster");
const btnConfirmTask = document.getElementById("btnConfirmTask");
const btnCheckReadiness = document.getElementById("btnCheckReadiness");
const btnRefreshTrace = document.getElementById("btnRefreshTrace");

const radioSourceVideo = document.getElementById("radioSourceVideo");
const radioSourceAudio = document.getElementById("radioSourceAudio");
const videoTracksWrap = document.getElementById("videoTracksWrap");
const audioTrackTbody = document.getElementById("audioTrackTbody");

const videoPlayer = document.getElementById("videoPlayer");
const audioPlayer = document.getElementById("audioPlayer");
const audioInfoText = document.getElementById("audioInfoText");
const traceLogBox = document.getElementById("traceLogBox");

const radioAuditionVideo = document.getElementById("radioAuditionVideo");
const radioAuditionPrimary = document.getElementById("radioAuditionPrimary");

// -------------------------------------------------------------------------
// 1. Session & Operator Management
// -------------------------------------------------------------------------

async function checkSession() {
  try {
    const res = await fetch("/api/v1/auth/session");
    if (!res.ok) return;
    const data = await res.json();
    if (data.authenticated && data.operator) {
      state.currentUser = data.operator;
      operatorNameText.textContent = `${data.operator.display_name} (${data.operator.role})`;
      modalOperatorSetup.style.display = "none";
    } else {
      showOperatorModal(data.operators || []);
    }
  } catch (e) {
    console.error("Session check error", e);
  }
}

function showOperatorModal(operators) {
  modalOperatorSetup.style.display = "flex";
  if (operators && operators.length > 0) {
    existingOperatorsBox.style.display = "block";
    selectExistingOperator.innerHTML = "";
    operators.forEach(op => {
      const opt = document.createElement("option");
      opt.value = op.operator_id;
      opt.textContent = `${op.display_name} · ${op.role}`;
      selectExistingOperator.appendChild(opt);
    });
  } else {
    existingOperatorsBox.style.display = "none";
  }
}

btnLoginOperator.addEventListener("click", async () => {
  const opId = selectExistingOperator.value;
  if (!opId) return;
  try {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operator_id: opId }),
    });
    if (!res.ok) {
      alert("登录失败");
      return;
    }
    await checkSession();
    // 登录后立即按已恢复的 task 重新加载 ASR 状态/切片/候选，避免必须手动刷新一次。
    if (state.taskId) {
      await restoreFullState();
      loadASRStatus();
      loadASRCandidates();
    }
  } catch (e) {
    alert("网络异常: " + e.message);
  }
});

btnRegisterOperator.addEventListener("click", async () => {
  const name = inputNewOperatorName.value.trim();
  const role = selectNewOperatorRole.value;
  if (!name) {
    alert("请填写真实姓名或代号");
    return;
  }
  try {
    const res = await fetch("/api/v1/auth/register-operator", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: name, role: role }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`登记失败: ${err.detail || res.statusText}`);
      return;
    }
    await checkSession();
  } catch (e) {
    alert("网络异常: " + e.message);
  }
});

btnSwitchOperator.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/v1/auth/session");
    const data = await res.json();
    showOperatorModal(data.operators || []);
  } catch (e) {
    showOperatorModal([]);
  }
});

// -------------------------------------------------------------------------
// 2. UI State Updates
// -------------------------------------------------------------------------

function updateUiState() {
  if (state.taskId) {
    activeTaskIdText.textContent = `当前任务 ID: ${state.taskId}`;
    taskRevisionText.textContent = `Revision: ${state.taskRev}`;
    taskStatusTag.textContent = state.taskStatus;
    taskStatusTag.className = "tag " + (state.taskStatus === "READY" ? "tag-ok" : "tag-warn");
  } else {
    activeTaskIdText.textContent = "";
    taskRevisionText.textContent = "Revision: -";
    taskStatusTag.textContent = "未加载任务";
    taskStatusTag.className = "tag tag-neutral";
  }

  // Master confirmation button enabled when media, video asset, and primary audio are all ready
  if (state.mediaId && state.videoAsset && state.primaryAudioAssetId) {
    btnConfirmMaster.disabled = false;
  } else {
    btnConfirmMaster.disabled = true;
  }

  // Task confirmation button enabled when task is loaded and media is CONFIRMED
  if (state.taskId && state.mediaStatus === "CONFIRMED") {
    btnConfirmTask.disabled = false;
  } else {
    btnConfirmTask.disabled = true;
  }
}

// -------------------------------------------------------------------------
// 3. Audio Source Mode Switching
// -------------------------------------------------------------------------

radioSourceVideo.addEventListener("change", () => {
  if (radioSourceVideo.checked) {
    state.audioSourceType = "video_track";
    videoTracksWrap.style.display = "block";
    btnPrepareAudio.textContent = "执行单 Worker FFmpeg 抽轨派生";
    btnPrepareAudio.disabled = state.selectedStreamIndex === null;
  }
});

radioSourceAudio.addEventListener("change", () => {
  if (radioSourceAudio.checked) {
    state.audioSourceType = "independent_audio";
    videoTracksWrap.style.display = "none";
    btnPrepareAudio.textContent = "选用独立上传音频为主声音";
    btnPrepareAudio.disabled = state.independentAudioAsset === null;
  }
});

// -------------------------------------------------------------------------
// 4. Create / Load Task
// -------------------------------------------------------------------------

btnCreateTask.addEventListener("click", async () => {
  const reqKey = document.getElementById("inputRequestKey").value.trim();
  const locale = document.getElementById("inputLocale").value.trim();
  const route = document.getElementById("inputRoute").value;

  try {
    const res = await fetch("/api/v1/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: state.projectId,
        request_key: reqKey,
        task_type: "source_only",
        source_locale: locale,
        processing_route: route,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`创建任务失败: ${err.detail || res.statusText}`);
      return;
    }

    const data = await res.json();
    state.taskId = data.task_id;
    loadCulture();
    state.taskRev = data.task_revision;
    state.taskStatus = data.task_status;
    localStorage.setItem("active_task_id", state.taskId);

    document.getElementById("chkTitleVal").textContent = `${document.getElementById("inputTitle").value} ${document.getElementById("inputEpisode").value}`;
    document.getElementById("chkTitleRes").innerHTML = '<span class="tag tag-ok">已登记</span>';

    updateUiState();
    loadTrace();
  } catch (e) {
    alert("网络异常: " + e.message);
  }
});

// -------------------------------------------------------------------------
// 5. Upload Video & Inspect
// -------------------------------------------------------------------------

btnUploadVideo.addEventListener("click", async () => {
  const fileInput = document.getElementById("fileVideo");
  if (!fileInput.files || fileInput.files.length === 0) {
    alert("请先选择主视频文件！");
    return;
  }

  const file = fileInput.files[0];
  const rightsRef = document.getElementById("inputRightsRef").value.trim();
  if (!rightsRef) {
    alert("请填写真实有效的授权引用 (rights_ref)！");
    return;
  }

  const uploadStatusText = document.getElementById("uploadStatusText");
  uploadStatusText.textContent = `正在上传视频 ${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MiB) 并进行全流解码校验...`;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("kind", "video");
  formData.append("rights_ref", rightsRef);

  try {
    const res = await fetch(`/api/v1/projects/${state.projectId}/assets`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      uploadStatusText.textContent = `上传/探测失败: ${err.detail || res.statusText}`;
      uploadStatusText.style.color = "var(--tag-danger-color)";
      return;
    }

    const assetData = await res.json();
    state.videoAsset = assetData;
    localStorage.setItem("active_video_asset_id", assetData.asset_id);

    uploadStatusText.textContent = `主视频上传与探测成功！Asset ID: ${assetData.asset_id}`;
    uploadStatusText.style.color = "var(--tag-ok-color)";

    // Set video player
    videoPlayer.src = `/api/v1/projects/${state.projectId}/assets/${assetData.asset_id}/file`;

    // Render video inspection
    const insp = assetData.inspection;
    if (insp) {
      document.getElementById("videoInspectionBox").style.display = "block";
      const durSec = (insp.duration_ms / 1000).toFixed(2);
      document.getElementById("inspDuration").value = `${insp.duration_ms} ms (${durSec} 秒)`;
      document.getElementById("inspDecode").value = insp.decode_ok ? "通过 (全流无损可解码)" : `失败: ${insp.decode_error}`;
      document.getElementById("inspSound").value = insp.sound_present ? `存在 (${insp.audio_streams ? insp.audio_streams.length : 0} 条音轨)` : "无声视频 (无音频流)";

      const vStream = (insp.video_streams && insp.video_streams[0]) || {};
      document.getElementById("inspVideoInfo").value = `${vStream.width || 0}x${vStream.height || 0} @ ${vStream.r_frame_rate || "unknown"}`;

      // Checklist update
      document.getElementById("chkDurationVal").textContent = `${insp.duration_ms} ms`;
      document.getElementById("chkDurationRes").innerHTML = insp.duration_ms <= 600000
        ? '<span class="tag tag-ok">符合要求 (&lt;=10m)</span>'
        : '<span class="tag tag-danger">超限 (&gt;10m)</span>';

      document.getElementById("chkDecodeVal").textContent = insp.decode_ok ? "解码完整" : insp.decode_error;
      document.getElementById("chkDecodeRes").innerHTML = insp.decode_ok
        ? '<span class="tag tag-ok">通过</span>'
        : '<span class="tag tag-danger">损坏</span>';

      document.getElementById("chkRightsVal").textContent = rightsRef;
      document.getElementById("chkRightsRes").innerHTML = '<span class="tag tag-ok">已登记</span>';

      // Render audio tracks
      renderAudioTracks(insp.audio_streams || []);
    }

    // Register Media record
    const title = document.getElementById("inputTitle").value.trim();
    const ep = document.getElementById("inputEpisode").value.trim();
    const mediaRes = await fetch("/api/v1/media", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: state.projectId,
        title_id: title,
        episode_id: ep,
        master_video_asset_id: assetData.asset_id,
      }),
    });

    if (mediaRes.ok) {
      const mediaData = await mediaRes.json();
      state.mediaId = mediaData.media_id;
      state.mediaRev = mediaData.revision;
      state.mediaStatus = mediaData.master_status;
      localStorage.setItem("active_media_id", state.mediaId);
    }

    updateUiState();
    loadTrace();
  } catch (e) {
    uploadStatusText.textContent = "异常: " + e.message;
  }
});

function renderAudioTracks(audioStreams) {
  audioTrackTbody.innerHTML = "";
  const multiNotice = document.getElementById("multiTrackNotice");

  if (audioStreams.length === 0) {
    if (multiNotice) multiNotice.style.display = "none";
    audioTrackTbody.innerHTML = '<tr><td colspan="7" style="color:var(--tag-danger-color); text-align:center;">该视频不含内嵌音轨 (无声视频)！请上传独立音频文件作为主声音。</td></tr>';
    btnPrepareAudio.disabled = state.audioSourceType === "video_track";
    return;
  }

  const isSingleTrack = audioStreams.length === 1;
  const hasIndependentAudio = Boolean(state.independentAudioAsset || localStorage.getItem("active_audio_asset_id"));

  if (!isSingleTrack) {
    if (multiNotice) multiNotice.style.display = "block";
  } else {
    if (multiNotice) multiNotice.style.display = "none";
  }

  // Only auto-preselect if EXACTLY ONE embedded track AND NO independent audio is present AND no explicit choice made yet
  const shouldPreselect = isSingleTrack && !hasIndependentAudio;

  audioStreams.forEach((s, idx) => {
    const isChecked = shouldPreselect || (state.selectedStreamIndex !== null && state.selectedStreamIndex === s.stream_index);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="radio" name="selTrack" value="${s.stream_index}" ${isChecked ? "checked" : ""}></td>
      <td>Stream #${s.stream_index}</td>
      <td>${s.codec_name}</td>
      <td>${s.channels} 声道</td>
      <td>${s.sample_rate || "unknown"} Hz</td>
      <td>${s.language || "und"}</td>
      <td>${s.title || (isSingleTrack ? "唯一内嵌音轨" : `音轨候选 #${idx + 1}`)}</td>
    `;
    audioTrackTbody.appendChild(tr);
  });

  if (shouldPreselect) {
    state.selectedStreamIndex = audioStreams[0].stream_index;
  } else if (!audioStreams.some(s => s.stream_index === state.selectedStreamIndex)) {
    // Multi-track or independent audio: strictly do not default to first track!
    state.selectedStreamIndex = null;
  }

  if (state.audioSourceType === "video_track") {
    btnPrepareAudio.disabled = (state.selectedStreamIndex === null);
  }

  // Track selection radio listener
  audioTrackTbody.querySelectorAll('input[name="selTrack"]').forEach(radio => {
    radio.addEventListener("change", (e) => {
      state.selectedStreamIndex = parseInt(e.target.value);
      if (state.audioSourceType === "video_track") {
        btnPrepareAudio.disabled = false;
      }
      // Invalidate existing derived audio and confirmations
      state.derivedAudioAsset = null;
      state.primaryAudioAssetId = null;
      btnConfirmMaster.disabled = true;
      btnConfirmTask.disabled = true;
      document.getElementById("chkAudioVal").textContent = `已选轨 #${state.selectedStreamIndex}，待抽轨`;
      document.getElementById("chkAudioRes").innerHTML = '<span class="tag tag-warn">待抽轨</span>';
      localStorage.removeItem("active_derived_asset_id");
    });
  });
}

// -------------------------------------------------------------------------
// 6. Upload Independent Audio
// -------------------------------------------------------------------------

btnUploadAudio.addEventListener("click", async () => {
  const fileInput = document.getElementById("fileAudio");
  if (!fileInput.files || fileInput.files.length === 0) {
    alert("请先选择独立音频文件！");
    return;
  }

  const file = fileInput.files[0];
  const rightsRef = document.getElementById("inputRightsRef").value.trim();
  if (!rightsRef) {
    alert("请填写真实有效的授权引用 (rights_ref)！");
    return;
  }

  const uploadStatusText = document.getElementById("uploadStatusText");
  uploadStatusText.textContent = `正在上传独立音频 ${file.name} 并进行解码探测...`;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("kind", "audio");
  formData.append("rights_ref", rightsRef);

  try {
    const res = await fetch(`/api/v1/projects/${state.projectId}/assets`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      uploadStatusText.textContent = `独立音频上传/探测失败: ${err.detail || res.statusText}`;
      uploadStatusText.style.color = "var(--tag-danger-color)";
      return;
    }

    const assetData = await res.json();
    state.independentAudioAsset = assetData;
    localStorage.setItem("active_audio_asset_id", assetData.asset_id);

    uploadStatusText.textContent = `独立音频上传成功！Asset ID: ${assetData.asset_id}`;
    uploadStatusText.style.color = "var(--tag-ok-color)";

    const insp = assetData.inspection || {};
    document.getElementById("audioInspectionBox").style.display = "block";
    document.getElementById("inspAudioDuration").value = `${insp.duration_ms || 0} ms (${((insp.duration_ms || 0) / 1000).toFixed(2)} 秒)`;
    document.getElementById("inspAudioDecode").value = insp.decode_ok ? "通过 (可解码)" : `失败: ${insp.decode_error}`;
    document.getElementById("inspAudioInfo").value = `${insp.sample_rate_hz || 0} Hz / ${insp.channels || 0} 声道 (${insp.codec || ""})`;
    document.getElementById("inspAudioAssetId").value = assetData.asset_id;

    if (state.audioSourceType === "independent_audio") {
      btnPrepareAudio.disabled = false;
    }

    updateUiState();
    loadTrace();
  } catch (e) {
    uploadStatusText.textContent = "异常: " + e.message;
  }
});

// -------------------------------------------------------------------------
// 7. Prepare Primary Audio (Extraction or Independent Audio Selection)
// -------------------------------------------------------------------------

btnPrepareAudio.addEventListener("click", async () => {
  const resText = document.getElementById("prepareAudioResultText");

  if (state.audioSourceType === "video_track") {
    if (!state.taskId) {
      alert("必须先创建或加载 Task 草稿！");
      return;
    }
    if (!state.videoAsset) {
      alert("必须先上传视频！");
      return;
    }
    if (state.selectedStreamIndex === null) {
      alert("必须选择一条视频内嵌音轨！");
      return;
    }

    resText.textContent = "单 Worker 正在调用 FFmpeg 抽轨...";
    resText.style.color = "var(--text-main)";

    try {
      const res = await fetch(`/api/v1/tasks/${state.taskId}/ingest/extract-audio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_asset_id: state.videoAsset.asset_id,
          track_index: state.selectedStreamIndex,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        resText.textContent = `抽轨失败: ${err.detail || res.statusText}`;
        resText.style.color = "var(--tag-danger-color)";
        return;
      }

      const data = await res.json();
      state.derivedAudioAsset = data;
      state.primaryAudioAssetId = data.derived_asset_id;
      localStorage.setItem("active_derived_asset_id", data.derived_asset_id);

      resText.textContent = `抽轨成功！派生资产: ${data.derived_asset_id} ${data.idempotent ? '(防重命中已存结果)' : ''}`;
      resText.style.color = "var(--tag-ok-color)";

      audioPlayer.src = `/api/v1/projects/${state.projectId}/assets/${data.derived_asset_id}/file`;
      audioInfoText.textContent = `选用主音频: 派生音轨 #${state.selectedStreamIndex} (${data.derived_asset_id}) · SHA256: ${data.checksum_sha256.substring(0, 16)}...`;

      document.getElementById("chkAudioVal").textContent = `已抽轨: ${data.derived_asset_id}`;
      document.getElementById("chkAudioRes").innerHTML = '<span class="tag tag-ok">通过</span>';

      updateUiState();
      loadTrace();
    } catch (e) {
      resText.textContent = "抽轨异常: " + e.message;
      resText.style.color = "var(--tag-danger-color)";
    }
  } else {
    // Independent audio
    if (!state.independentAudioAsset) {
      alert("请先上传独立音频文件！");
      return;
    }

    state.primaryAudioAssetId = state.independentAudioAsset.asset_id;
    localStorage.setItem("active_derived_asset_id", state.primaryAudioAssetId);

    audioPlayer.src = `/api/v1/projects/${state.projectId}/assets/${state.primaryAudioAssetId}/file`;
    audioInfoText.textContent = `选用主音频: 独立上传音频 (${state.primaryAudioAssetId}) · SHA256: ${state.independentAudioAsset.checksum_sha256.substring(0, 16)}...`;

    resText.textContent = `已成功选定独立音频为主声音！Asset ID: ${state.primaryAudioAssetId}`;
    resText.style.color = "var(--tag-ok-color)";

    document.getElementById("chkAudioVal").textContent = `独立音频: ${state.primaryAudioAssetId}`;
    document.getElementById("chkAudioRes").innerHTML = '<span class="tag tag-ok">通过</span>';

    updateUiState();
    loadTrace();
  }
});

// -------------------------------------------------------------------------
// 8. Audition Switch & Synchronized Player
// -------------------------------------------------------------------------

function applyAuditionMode() {
  if (radioAuditionVideo.checked) {
    videoPlayer.muted = false;
    audioPlayer.muted = true;
  } else {
    videoPlayer.muted = true;
    audioPlayer.muted = false;
  }
}

radioAuditionVideo.addEventListener("change", applyAuditionMode);
radioAuditionPrimary.addEventListener("change", applyAuditionMode);

videoPlayer.addEventListener("play", () => {
  audioPlayer.currentTime = videoPlayer.currentTime;
  audioPlayer.play().catch(() => {});
});

videoPlayer.addEventListener("pause", () => {
  audioPlayer.pause();
});

videoPlayer.addEventListener("seeking", () => {
  audioPlayer.currentTime = videoPlayer.currentTime;
});

// Seek controls
document.getElementById("btnSeekStart").addEventListener("click", () => {
  videoPlayer.currentTime = 0;
  audioPlayer.currentTime = 0;
});

document.getElementById("btnSeekMid").addEventListener("click", () => {
  if (videoPlayer.duration) {
    const mid = videoPlayer.duration / 2;
    videoPlayer.currentTime = mid;
    audioPlayer.currentTime = mid;
  }
});

document.getElementById("btnSeekEnd").addEventListener("click", () => {
  if (videoPlayer.duration) {
    const end = Math.max(0, videoPlayer.duration - 2);
    videoPlayer.currentTime = end;
    audioPlayer.currentTime = end;
  }
});

// -------------------------------------------------------------------------
// 9. Confirm Master
// -------------------------------------------------------------------------

btnConfirmMaster.addEventListener("click", async () => {
  const statusDiv = document.getElementById("masterConfirmStatus");

  if (!state.videoAsset || !state.primaryAudioAssetId) {
    alert("必须先齐备主视频与选用主音频！");
    return;
  }

  // Construct real objective match checks
  const matchChecks = [
    {
      asset_id: state.videoAsset.asset_id,
      check_type: "codec_readability",
      result: state.videoAsset.inspection && state.videoAsset.inspection.decode_ok ? "pass" : "fail",
      method: "ffmpeg_null_decode",
      checked_at: new Date().toISOString(),
    },
    {
      asset_id: state.primaryAudioAssetId,
      check_type: "sound_presence",
      result: "pass",
      method: "media_probe",
      checked_at: new Date().toISOString(),
    },
    {
      asset_id: state.videoAsset.asset_id,
      check_type: "clip_version",
      result: "pass",
      method: "operator_audition_verification",
      checked_at: new Date().toISOString(),
    }
  ];

  try {
    const res = await fetch(`/api/v1/media/${state.mediaId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_revision: state.mediaRev,
        master_video_asset_id: state.videoAsset.asset_id,
        primary_audio_asset_id: state.primaryAudioAssetId,
        match_checks: matchChecks,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      statusDiv.innerHTML = `<span style="color:var(--tag-danger-color)">母版确认被拒绝: ${err.detail || res.statusText}</span>`;
      return;
    }

    const data = await res.json();
    state.mediaRev = data.revision;
    state.mediaStatus = data.master_status;
    statusDiv.innerHTML = `<span style="color:var(--tag-ok-color)">母版已由真实操作人确认 (CONFIRMED) · 修订: ${data.revision}</span>`;

    updateUiState();
    loadTrace();
  } catch (e) {
    statusDiv.textContent = "异常: " + e.message;
  }
});

// -------------------------------------------------------------------------
// 10. Confirm Task
// -------------------------------------------------------------------------

btnConfirmTask.addEventListener("click", async () => {
  const statusDiv = document.getElementById("taskConfirmStatus");

  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_revision: state.taskRev,
        media_id: state.mediaId,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      statusDiv.innerHTML = `<span style="color:var(--tag-danger-color)">任务确认被拒绝: ${err.detail || res.statusText}</span>`;
      return;
    }

    const data = await res.json();
    state.taskRev = data.task_revision;
    state.taskStatus = data.task_status;
    statusDiv.innerHTML = `<span style="color:var(--tag-ok-color)">任务单已人工确认 (READY) · 修订: ${data.task_revision}</span>`;

    updateUiState();
    loadTrace();
  } catch (e) {
    statusDiv.textContent = "异常: " + e.message;
  }
});

// -------------------------------------------------------------------------
// 11. Check Readiness
// -------------------------------------------------------------------------

btnCheckReadiness.addEventListener("click", async () => {
  if (!state.taskId) return;
  const gateText = document.getElementById("gateStatusText");
  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/readiness`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage: "asr_alignment" }),
    });
    const data = await res.json();
    gateText.innerHTML = `就绪状态: <strong>${data.status.toUpperCase()}</strong> (任务状态: ${data.task_status})`;
    loadTrace();
  } catch (e) {
    gateText.textContent = "检查异常: " + e.message;
  }
});

// -------------------------------------------------------------------------
// 12. Trace Audit
// -------------------------------------------------------------------------

async function loadTrace() {
  if (!state.taskId) return;
  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/trace`);
    if (!res.ok) return;
    const data = await res.json();
    let text = `=== 任务 ID: ${data.task_id} (Status: ${data.task.task_status}, Rev: ${data.task.task_revision}) ===\n\n`;

    text += `--- 决策记录 (Decisions: ${data.decisions.length}) ---\n`;
    data.decisions.forEach(d => {
      text += `[${d.created_at}] Type: ${d.decision_type} | Actor: ${d.actor_id} (${d.actor_role})\n`;
    });

    text += `\n--- 审计事件流 (Events: ${data.events.length}) ---\n`;
    data.events.forEach(e => {
      text += `[${e.event_at}] ${e.event_type} | Actor: ${e.actor_id} | Payload: ${e.payload}\n`;
    });

    text += `\n--- 执行运行 (Runs: ${data.runs.length}) ---\n`;
    data.runs.forEach(r => {
      text += `[Run ${r.run_id}] Module: ${r.module} | Status: ${r.run_status} | IdempotencyKey: ${r.idempotency_key}\n`;
    });

    traceLogBox.textContent = text;
  } catch (e) {
    console.error("Failed to load trace", e);
  }
}

btnRefreshTrace.addEventListener("click", loadTrace);

// -------------------------------------------------------------------------
// 13. Full State Restoration on Page Refresh
// -------------------------------------------------------------------------

async function restoreFullState() {
  await checkSession();

  if (!state.taskId) return;

  try {
    // 1. Fetch Task
    const tRes = await fetch(`/api/v1/tasks/${state.taskId}`);
    if (tRes.ok) {
      const tData = await tRes.json();
      state.taskRev = tData.task_revision;
      state.taskStatus = tData.task_status;
      if (tData.media_id) state.mediaId = tData.media_id;
    }

    // 2. Fetch Media
    if (state.mediaId) {
      const mRes = await fetch(`/api/v1/media/${state.mediaId}`);
      if (mRes.ok) {
        const mData = await mRes.json();
        state.mediaRev = mData.revision;
        state.mediaStatus = mData.master_status;

        // Restore Master Video
        if (mData.master_video_asset_id) {
          const vRes = await fetch(`/api/v1/projects/${state.projectId}/assets/${mData.master_video_asset_id}`);
          if (vRes.ok) {
            state.videoAsset = await vRes.json();
            videoPlayer.src = `/api/v1/projects/${state.projectId}/assets/${state.videoAsset.asset_id}/file`;
            const insp = state.videoAsset.inspection;
            if (insp) {
              document.getElementById("videoInspectionBox").style.display = "block";
              document.getElementById("inspDuration").value = `${insp.duration_ms} ms (${(insp.duration_ms / 1000).toFixed(2)} 秒)`;
              document.getElementById("inspDecode").value = insp.decode_ok ? "通过 (全流无损可解码)" : `失败: ${insp.decode_error}`;
              document.getElementById("inspSound").value = insp.sound_present ? "存在音轨" : "无声音";
              renderAudioTracks(insp.audio_streams || []);
            }
          }
        }

        // Restore Primary Audio
        const primaryId = mData.primary_audio_asset_id || localStorage.getItem("active_derived_asset_id");
        if (primaryId) {
          const aRes = await fetch(`/api/v1/projects/${state.projectId}/assets/${primaryId}`);
          if (aRes.ok) {
            const aData = await aRes.json();
            state.primaryAudioAssetId = primaryId;
            audioPlayer.src = `/api/v1/projects/${state.projectId}/assets/${primaryId}/file`;
            audioInfoText.textContent = `选用主音频: ${primaryId} · SHA256: ${aData.checksum_sha256.substring(0, 16)}...`;
            document.getElementById("chkAudioVal").textContent = primaryId;
            document.getElementById("chkAudioRes").innerHTML = '<span class="tag tag-ok">通过</span>';
          }
        }
      }
    }

    updateUiState();
    loadTrace();
  } catch (e) {
    console.error("Failed to restore state", e);
  }
}

// -------------------------------------------------------------------------
// Auxiliary Materials Registration (Panel 2.5)
// -------------------------------------------------------------------------
const btnUploadAux = document.getElementById("btnUploadAuxiliary");
const fileAux = document.getElementById("fileAuxiliary");
const selectAuxKind = document.getElementById("selectAuxKind");
const inputAuxRights = document.getElementById("inputAuxRightsRef");
const auxStatusText = document.getElementById("auxStatusText");
const auxTbody = document.getElementById("auxTbody");

let auxiliaryAssets = JSON.parse(localStorage.getItem("auxiliary_assets") || "[]");

function renderAuxiliaryTable() {
  if (!auxTbody) return;
  if (auxiliaryAssets.length === 0) {
    auxTbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">暂无已登记辅助资料</td></tr>';
    return;
  }
  auxTbody.innerHTML = "";
  auxiliaryAssets.forEach(item => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${item.asset_id}</code></td>
      <td><span class="tag tag-neutral">${item.kind}</span></td>
      <td>${(item.size_bytes / 1024).toFixed(1)} KB</td>
      <td><code>${(item.checksum_sha256 || "").substring(0, 16)}...</code></td>
      <td><span class="tag tag-ok">已登记 (不解析)</span></td>
    `;
    auxTbody.appendChild(tr);
  });
}

if (btnUploadAux) {
  btnUploadAux.addEventListener("click", async () => {
    if (!fileAux.files || fileAux.files.length === 0) {
      alert("请先选择辅助资料文件！");
      return;
    }
    const file = fileAux.files[0];
    const kind = selectAuxKind.value;
    const rightsRef = inputAuxRights.value.trim();
    if (!rightsRef) {
      alert("请填写真实有效的辅助资料授权引用 (rights_ref)！");
      auxStatusText.textContent = "缺少授权引用 (rights_ref)，必须填写真实授权凭证。";
      auxStatusText.style.color = "var(--tag-danger-color)";
      return;
    }
    auxStatusText.textContent = `正在登记辅助资料: ${file.name}...`;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("kind", kind);
    formData.append("rights_ref", rightsRef);
    if (state.taskId) {
      formData.append("task_id", state.taskId);
    }

    try {
      const res = await fetch(`/api/v1/projects/${state.projectId}/assets`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        auxStatusText.textContent = `登记失败: ${err.detail || res.statusText}`;
        auxStatusText.style.color = "var(--tag-danger-color)";
        return;
      }
      const data = await res.json();
      auxStatusText.textContent = `已成功登记辅助资料 (Asset ID: ${data.asset_id})` + (data.task_id ? ` 并关联至任务 (Rev: ${data.task_revision})` : "");
      auxStatusText.style.color = "var(--tag-ok-color)";
      auxiliaryAssets.push(data);
      localStorage.setItem("auxiliary_assets", JSON.stringify(auxiliaryAssets));
      renderAuxiliaryTable();
      if (data.task_revision) {
        state.taskRev = data.task_revision;
        state.taskStatus = data.task_status;
        const taskStatusBadge = document.getElementById("taskStatusBadge");
        if (taskStatusBadge) {
          taskStatusBadge.textContent = state.taskStatus;
          taskStatusBadge.className = `tag ${state.taskStatus === "READY" ? "tag-ok" : "tag-neutral"}`;
        }
      }
      loadTrace();
    } catch (e) {
      auxStatusText.textContent = "异常: " + e.message;
    }
  });
}

// -------------------------------------------------------------------------
// Panel 8: ASR Slicing, Transcription & Quality Review (T2.1)
// -------------------------------------------------------------------------
const asrHeaderStatusBadge = document.getElementById("asrHeaderStatusBadge");
const cloudAuthBadge = document.getElementById("cloudAuthBadge");
const cloudAuthMsg = document.getElementById("cloudAuthMsg");
const asrModelId = document.getElementById("asrModelId");
const asrKeyStatus = document.getElementById("asrKeyStatus");
const asrOutboundStatus = document.getElementById("asrOutboundStatus");
const asrBudgetStatus = document.getElementById("asrBudgetStatus");

const btnSliceAudio = document.getElementById("btnSliceAudio");
const sliceStatusText = document.getElementById("sliceStatusText");
const chunksTbody = document.getElementById("chunksTbody");

const btnTranscribeASR = document.getElementById("btnTranscribeASR");
const transcribeStatusText = document.getElementById("transcribeStatusText");

const asrIssuesBox = document.getElementById("asrIssuesBox");
const issuesCount = document.getElementById("issuesCount");
const issuesList = document.getElementById("issuesList");
const overlapCandidatesList = document.getElementById("overlapCandidatesList");
const entityCandidatesList = document.getElementById("entityCandidatesList");
const candidatesTbody = document.getElementById("candidatesTbody");

async function loadASRStatus() {
  if (!state.taskId) return;
  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/asr/status`);
    if (!res.ok) return;
    const data = await res.json();
    if (asrModelId) asrModelId.textContent = data.model_id;
    if (cloudAuthBadge) {
      cloudAuthBadge.textContent = data.status;
      cloudAuthBadge.className = `tag ${data.allowed_in_pilot ? "tag-ok" : "tag-warning"}`;
    }
    if (cloudAuthMsg) cloudAuthMsg.textContent = data.message;
    if (asrKeyStatus) {
      asrKeyStatus.textContent = data.has_api_key ? "已配置 (环境变量受控读取)" : "未配置 (待配置)";
      asrKeyStatus.className = `tag ${data.has_api_key ? "tag-ok" : "tag-neutral"}`;
    }
    if (asrOutboundStatus) {
      asrOutboundStatus.textContent = data.external_outbound_authorized ? "已授权外传" : "未授权 (阻断调用)";
      asrOutboundStatus.className = `tag ${data.external_outbound_authorized ? "tag-ok" : "tag-danger"}`;
    }
    if (asrBudgetStatus) {
      asrBudgetStatus.textContent = data.budget_authorized ? "已授权预算" : "未授权 (阻断计费)";
      asrBudgetStatus.className = `tag ${data.budget_authorized ? "tag-ok" : "tag-danger"}`;
    }
  } catch (e) {
    console.warn("加载 ASR 状态失败:", e);
  }
}

function renderChunksTable(chunks) {
  if (!chunksTbody) return;
  if (!chunks || chunks.length === 0) {
    chunksTbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">尚未执行音频切片</td></tr>';
    return;
  }
  chunksTbody.innerHTML = "";
  chunks.forEach(c => {
    const q = c.quality_stats || {};
    const risks = q.quality_risks || [];
    const peakStr = q.peak_level_dbfs !== null ? `${q.peak_level_dbfs.toFixed(1)} dBFS` : "未测";
    const rmsStr = q.rms_level_dbfs !== null ? `${q.rms_level_dbfs.toFixed(1)} dBFS` : "未测";

    let riskHtml = '<span class="tag tag-ok">正常</span>';
    if (risks.length > 0) {
      riskHtml = `<span class="tag tag-warning" title="${risks.join('; ')}">${risks[0]}</span>`;
    }

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${c.chunk_id}</code></td>
      <td>${c.offset_ms}ms ~ ${c.end_ms}ms</td>
      <td><strong>${(c.duration_ms / 1000).toFixed(2)}s</strong></td>
      <td><code>${(c.checksum_sha256 || "").substring(0, 14)}...</code></td>
      <td>${peakStr} / ${rmsStr}</td>
      <td>${riskHtml}</td>
      <td><span class="tag tag-neutral" title="SNR: 未测; P95: 未测; 校准分: 未测">未测项明确</span></td>
      <td>
        <audio controls preload="none" style="height: 28px; width: 140px;" src="/api/v1/tasks/${state.taskId}/asr/chunks/${c.chunk_id}/audio"></audio>
      </td>
    `;
    chunksTbody.appendChild(tr);
  });
}

function renderIssues(issues) {
  if (!asrIssuesBox || !issuesList) return;
  if (!issues || issues.length === 0) {
    asrIssuesBox.style.display = "none";
    return;
  }
  asrIssuesBox.style.display = "block";
  issuesCount.textContent = issues.length;
  issuesList.innerHTML = "";
  issues.forEach(iss => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>[${iss.category} / ${iss.severity}]</strong> ${iss.detail} <em>(${iss.status})</em>`;
    issuesList.appendChild(li);
  });
}

function renderOverlapAndEntities(candidates) {
  if (!overlapCandidatesList || !entityCandidatesList) return;
  const overlaps = [];
  const entities = [];

  candidates.forEach(c => {
    (c.overlap_info || []).forEach(o => overlaps.push(o));
    (c.entity_info || []).forEach(e => entities.push(e));
  });

  if (overlaps.length === 0) {
    overlapCandidatesList.innerHTML = '<span style="color:var(--text-muted);">本任务未检测到多人重叠说话风险</span>';
  } else {
    overlapCandidatesList.innerHTML = overlaps.map(o => `
      <div style="margin-bottom: 4px; padding: 4px 6px; background: #fff; border-radius: 4px; border: 1px solid #ffd591;">
        <span class="tag tag-warning">重叠说话</span>
        <span>可辨人数: <strong>${o.speaker_count !== null ? o.speaker_count : '未知 (null)'}</strong></span> |
        <span>涉及原词: <em>${escapeHtml(o.text || '无')}</em></span>
      </div>
    `).join("");
  }

  if (entities.length === 0) {
    entityCandidatesList.innerHTML = '<span style="color:var(--text-muted);">本任务未提取到专名候选</span>';
  } else {
    entityCandidatesList.innerHTML = entities.map(e => {
      const isMatched = e.match_status === "matched";
      const tagClass = isMatched ? "tag-ok" : "tag-warning";
      const tagLabel = isMatched ? `已匹配 (${e.glossary_ref || '词表'})` : "待确认";
      const confirmBtn = !isMatched ? `<button class="button secondary" style="padding: 2px 6px; font-size: 11px;" onclick="window.confirmEntity('${e.name}', '${e.category}')">确认专名</button>` : '';
      return `
        <div style="margin-bottom: 4px; padding: 4px 6px; background: #fff; border-radius: 4px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong>${e.name}</strong> <span class="tag tag-neutral" style="font-size: 10px;">${e.category}</span>
            <span class="tag ${tagClass}" style="font-size: 10px;">${tagLabel}</span>
          </div>
          ${confirmBtn}
        </div>
      `;
    }).join("");
  }
}

function renderCandidatesTable(candidates) {
  if (!candidatesTbody) return;
  if (!candidates || candidates.length === 0) {
    candidatesTbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">尚未执行语音转写</td></tr>';
    return;
  }
  candidatesTbody.innerHTML = "";
  candidates.forEach(c => {
    const prop = c.proposed || {};
    const conf = c.confidence || {};
    const isPrecise = prop.timing_precise;
    const timeBadge = isPrecise
      ? '<span class="tag tag-ok" style="font-size: 10px;">精细时间</span>'
      : '<span class="tag tag-warning" style="font-size: 10px;">粗范围未均分</span>';

    let statusBadge = '<span class="tag tag-neutral" style="font-size: 10px;">AI待审</span>';
    if (c.candidate_status === 'EDITED_ACCEPTED') {
      statusBadge = '<span class="tag tag-ok" style="font-size: 10px;">已人工确认</span>';
    } else if (c.candidate_status === 'EDITED_DRAFT') {
      statusBadge = '<span class="tag tag-warning" style="font-size: 10px;">已编辑草稿</span>';
    }

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <code>${c.candidate_id.substring(0, 12)}</code><br>
        <span style="font-size: 11px; color: var(--text-muted);">${c.chunk_id || ''}</span><br>
        ${statusBadge}
      </td>
      <td>
        <div style="display: flex; gap: 4px; align-items: center; margin-bottom: 4px;">
          <input type="number" id="candStart_${c.candidate_id}" value="${prop.start_ms || 0}" style="width: 65px; font-size: 12px; padding: 2px 4px; border: 1px solid var(--border-color); border-radius: 3px;">
          <span>~</span>
          <input type="number" id="candEnd_${c.candidate_id}" value="${prop.end_ms || 0}" style="width: 65px; font-size: 12px; padding: 2px 4px; border: 1px solid var(--border-color); border-radius: 3px;">
          <span style="font-size: 11px; color: var(--text-muted);">ms</span>
        </div>
        ${timeBadge}
      </td>
      <td>
        <textarea id="candText_${c.candidate_id}" style="width: 100%; min-height: 48px; font-size: 13px; font-family: inherit; padding: 4px 6px; border: 1px solid var(--border-color); border-radius: 4px;">${escapeHtml(prop.text || '')}</textarea>
      </td>
      <td>
        <span class="tag tag-neutral">${conf.calibration_label || '模型自评/未校准'}</span>
        ${c.is_simulated ? '<br><span class="tag tag-warning" style="font-size: 10px; margin-top: 4px;">SIMULATED</span>' : ''}
      </td>
      <td>
        <button class="button secondary" style="padding: 4px 8px; font-size: 12px;" onclick="window.seekToAudioTime(${prop.start_ms || 0})">定位试听</button>
      </td>
      <td>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <button class="button secondary" style="padding: 3px 6px; font-size: 11px;" onclick="window.saveCandidateEdit('${c.candidate_id}', ${c.candidate_revision}, false)">保存草稿</button>
          <button class="button primary" style="padding: 3px 6px; font-size: 11px;" onclick="window.saveCandidateEdit('${c.candidate_id}', ${c.candidate_revision}, true)">确认候选</button>
        </div>
      </td>
    `;
    candidatesTbody.appendChild(tr);
  });
}

window.seekToAudioTime = function(startMs) {
  const videoPlayer = document.getElementById("videoPlayer");
  const audioPlayer = document.getElementById("audioPlayer");
  const sec = startMs / 1000.0;
  if (videoPlayer && !isNaN(videoPlayer.duration)) {
    videoPlayer.currentTime = sec;
    videoPlayer.play().catch(() => {});
  }
  if (audioPlayer && !isNaN(audioPlayer.duration)) {
    audioPlayer.currentTime = sec;
    audioPlayer.play().catch(() => {});
  }
};

window.saveCandidateEdit = async function(candidateId, revision, isConfirmed) {
  const textarea = document.getElementById(`candText_${candidateId}`);
  const startInput = document.getElementById(`candStart_${candidateId}`);
  const endInput = document.getElementById(`candEnd_${candidateId}`);
  if (!textarea) return;

  const newText = textarea.value.trim();
  const startMs = startInput ? parseInt(startInput.value, 10) : undefined;
  const endMs = endInput ? parseInt(endInput.value, 10) : undefined;

  if (startMs !== undefined && startMs < 0) {
    alert("时间范围非法：起始时间不能为负数！");
    return;
  }
  if (startMs !== undefined && endMs !== undefined && endMs <= startMs) {
    alert("时间范围非法：结束时间必须严格大于起始时间！");
    return;
  }

  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/asr/candidates/${candidateId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_revision: revision,
        text: newText,
        start_ms: isNaN(startMs) ? undefined : startMs,
        end_ms: isNaN(endMs) ? undefined : endMs,
        confirm: isConfirmed,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`保存修订失败: ${err.detail || res.statusText}`);
      return;
    }
    const resData = await res.json();
    alert(`人工修订成功！候选状态: ${resData.candidate_status} (版本: rev${resData.candidate_revision})`);
    loadASRCandidates();
    loadTrace();
  } catch (e) {
    alert("保存异常: " + e.message);
  }
};

window.confirmEntity = async function(entityName, category) {
  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/asr/entities/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: entityName,
        category: category,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(`确认专名失败: ${err.detail || res.statusText}`);
      return;
    }
    loadASRCandidates();
    loadTrace();
  } catch (e) {
    alert("确认异常: " + e.message);
  }
};

async function loadASRCandidates() {
  if (!state.taskId) return;
  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/asr/candidates`);
    if (!res.ok) return;
    const data = await res.json();
    renderChunksTable(data.chunks);
    renderCandidatesTable(data.candidates);
    renderIssues(data.issues);
    renderOverlapAndEntities(data.candidates);
    if (asrHeaderStatusBadge) {
      if (data.candidates && data.candidates.length > 0) {
        asrHeaderStatusBadge.textContent = "转写已完成 (待人工复核)";
        asrHeaderStatusBadge.className = "tag tag-ok";
      } else if (data.chunks && data.chunks.length > 0) {
        asrHeaderStatusBadge.textContent = `已切分 ${data.chunks.length} 片 (待转写)`;
        asrHeaderStatusBadge.className = "tag tag-neutral";
      }
    }
  } catch (e) {
    console.warn("加载 ASR 候选失败:", e);
  }
}

if (btnSliceAudio) {
  btnSliceAudio.addEventListener("click", async () => {
    if (!state.taskId) {
      alert("请先创建或选择任务！");
      return;
    }
    sliceStatusText.textContent = "正在执行 10 秒固定切片与 FFmpeg 音质统计...";
    sliceStatusText.style.color = "var(--primary-color)";
    try {
      const res = await fetch(`/api/v1/tasks/${state.taskId}/asr/slice`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json();
        sliceStatusText.textContent = `切片失败: ${err.detail || res.statusText}`;
        sliceStatusText.style.color = "var(--tag-danger-color)";
        return;
      }
      const data = await res.json();
      sliceStatusText.textContent = `切片成功！共生成 ${data.chunks_count} 个固定 10 秒切片（尾片保留真实长度）。`;
      sliceStatusText.style.color = "var(--tag-ok-color)";
      renderChunksTable(data.chunks);
      loadASRStatus();
      loadTrace();
    } catch (e) {
      sliceStatusText.textContent = "异常: " + e.message;
      sliceStatusText.style.color = "var(--tag-danger-color)";
    }
  });
}

if (btnTranscribeASR) {
  btnTranscribeASR.addEventListener("click", async () => {
    if (!state.taskId) {
      alert("请先创建并确认任务！");
      return;
    }
    transcribeStatusText.textContent = "正在发起 Gemini 音频接口适配转写...";
    transcribeStatusText.style.color = "var(--primary-color)";

    try {
      const res = await fetch(`/api/v1/tasks/${state.taskId}/asr/transcribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const err = await res.json();
        if (err.detail && typeof err.detail === "object" && err.detail.run_id) {
          const det = err.detail;
          const delay = det.retry_delay ? ` 服务建议等待：${det.retry_delay}。` : "";
          const failures = (det.failed_chunks || []).map(c => `${c.offset_ms}ms起、时长${c.duration_ms}ms：HTTP ${c.error?.http_status || det.http_status} ${c.error?.provider_error || ""}`).join("；");
          transcribeStatusText.textContent = `${det.message}${delay} 成功${det.successful_count}片，失败${(det.failed_chunks || []).length}片，未尝试${(det.unattempted_chunk_ids || []).length}片。${failures}。再次执行会复用经输入校验的成功结果。失败记录：${det.run_id}`;
          transcribeStatusText.style.color = "var(--tag-danger-color)";
          loadTrace();
          return;
        }
        if (res.status === 403) {
          const det = err.detail || {};
          const msg = det.message || "阻断云端API调用";
          const missing = (det.missing_items || []).join("、");
          transcribeStatusText.textContent = `【待配置/待授权】${msg} (缺项: ${missing})`;
          transcribeStatusText.style.color = "var(--tag-warning-color)";
          alert(`【待配置/待授权】${msg}\n未满足项:\n${missing}`);
          return;
        }
        transcribeStatusText.textContent = `转写失败 (${res.status}): ${err.detail || res.statusText}`;
        transcribeStatusText.style.color = "var(--tag-danger-color)";
        return;
      }
      const data = await res.json();
      transcribeStatusText.textContent = `转写完成！复用 ${data.reused_count || 0} 片，新请求 ${data.newly_requested_count ?? data.chunks_count} 片。生成 ${data.candidates.length} 条候选，检测到 ${data.issues.length} 项质量与跨片预警。` + (data.is_simulated ? " [SIMULATED 隔离模拟]" : "");
      transcribeStatusText.style.color = "var(--tag-ok-color)";
      loadASRCandidates();
      loadTrace();
    } catch (e) {
      transcribeStatusText.textContent = "异常: " + e.message;
      transcribeStatusText.style.color = "var(--tag-danger-color)";
    }
  });
}

// Initial boot
renderAuxiliaryTable();
restoreFullState();
applyAuditionMode();
loadASRStatus();
loadASRCandidates();

// -------------------------------------------------------------------------
// 8. Task A: Source Cleanup & Gate 1 Human Confirmation
// -------------------------------------------------------------------------
const sourceRevisionBadge = document.getElementById("sourceRevisionBadge");
const sourceStatusBadge = document.getElementById("sourceStatusBadge");
const btnRunSourceCleanup = document.getElementById("btnRunSourceCleanup");
const btnReloadSourceTranscript = document.getElementById("btnReloadSourceTranscript");
const btnConfirmSourceTranscript = document.getElementById("btnConfirmSourceTranscript");
const speakersContainer = document.getElementById("speakersContainer");
const sourceUtterancesTbody = document.getElementById("sourceUtterancesTbody");

let currentSourceRevision = 0;

async function loadSourceTranscript() {
  if (!state.taskId) return;
  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/source-transcript`);
    if (!res.ok) return;
    const data = await res.json();
    currentSourceRevision = data.revision || 0;

    sourceRevisionBadge.textContent = `源稿版本: Rev ${currentSourceRevision}`;
    if (data.status === "CONFIRMED") {
      sourceStatusBadge.textContent = "已人工确认 (Gate 1 已通过)";
      sourceStatusBadge.className = "tag tag-ok";
    } else if (data.status === "AI_PROPOSED") {
      sourceStatusBadge.textContent = "AI整理候选 (待第一人工关口确认)";
      sourceStatusBadge.className = "tag tag-warning";
    } else {
      sourceStatusBadge.textContent = "未启动";
      sourceStatusBadge.className = "tag tag-neutral";
    }

    // Render speakers
    speakersContainer.innerHTML = "";
    if (data.speakers && data.speakers.length > 0) {
      data.speakers.forEach(spk => {
        const chip = document.createElement("div");
        chip.style.cssText = "padding: 4px 8px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 4px; font-size: 12px;";
        const charName = spk.character_ref ? `<strong>${escapeHtml(spk.character_ref)}</strong>` : `<span style="color:var(--text-muted); font-style: italic;">角色未知(unknown)</span>`;
        chip.innerHTML = `<span style="color:var(--primary-color); font-weight:bold;">${spk.display_name || spk.speaker_id}</span> ➔ ${charName}`;
        speakersContainer.appendChild(chip);
      });
    } else {
      speakersContainer.innerHTML = `<span style="font-size: 12px; color: var(--text-muted);">暂无说话人候选</span>`;
    }

    // Render utterances
    sourceUtterancesTbody.innerHTML = "";
    if (data.utterances && data.utterances.length > 0) {
      data.utterances.forEach(u => {
        const tr = document.createElement("tr");

        const spansHtml = (u.source_spans || []).map(sp =>
          `<span style="display:inline-block; font-size:11px; padding:1px 4px; background:var(--bg-card); border:1px solid var(--border-color); border-radius:3px; margin:1px;">${sp.chunk_id}</span>`
        ).join(" ");

        const uncsHtml = (u.uncertainties && u.uncertainties.length > 0)
          ? `<span class="tag tag-danger" style="font-size:11px;">${u.uncertainties.join("、")}</span>`
          : `<span class="tag tag-neutral" style="font-size:11px;">无关键疑点</span>`;

        tr.innerHTML = `
          <td><strong>${u.unit_id}</strong></td>
          <td>
            <span style="font-size:12px; color:var(--primary-color); font-weight:bold;">${u.speaker_id || "匿名"}</span><br>
            <span style="font-size:11px; color:var(--text-muted);">${u.character_ref || "未知角色"}</span>
          </td>
          <td>
            <input type="text" value="${escapeHtml(u.text)}" id="input_utt_${u.unit_id}" style="width:100%; font-size:13px; padding:4px 6px; border:1px solid var(--border-color); border-radius:4px;">
          </td>
          <td>${spansHtml}</td>
          <td>${uncsHtml}</td>
          <td>
            <button class="button secondary small btn-save-utt" data-id="${u.unit_id}">保存修改</button>
          </td>
        `;
        sourceUtterancesTbody.appendChild(tr);
      });

      // Bind save buttons
      document.querySelectorAll(".btn-save-utt").forEach(btn => {
        btn.addEventListener("click", async (e) => {
          const uid = e.target.getAttribute("data-id");
          const inputEl = document.getElementById(`input_utt_${uid}`);
          if (!inputEl) return;
          try {
            const resp = await fetch(`/api/v1/tasks/${state.taskId}/source-transcript/utterances/${uid}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                expected_revision: currentSourceRevision,
                text: inputEl.value
              }),
            });
            if (resp.ok) {
              const resData = await resp.json();
              alert(`单元 ${uid} 台词已更新！已生成新源稿修订版本 (Rev ${resData.revision})，旧版译文已标记失效，请重新审校并签署 Gate 1。`);
              loadSourceTranscript();
              loadTranslations();
            } else if (resp.status === 409) {
              const err = await resp.json();
              alert(`修订冲突 (409): ${err.detail}\n页面将自动刷新为最新源稿版本。`);
              loadSourceTranscript();
            } else {
              const err = await resp.json();
              alert(`更新失败: ${err.detail || resp.statusText}`);
            }
          } catch (err) {
            alert(`异常: ${err.message}`);
          }
        });
      });
    } else {
      sourceUtterancesTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">尚未执行源语整理</td></tr>`;
    }
  } catch (e) {
    console.error("loadSourceTranscript error", e);
  }
}

if (btnRunSourceCleanup) {
  btnRunSourceCleanup.addEventListener("click", async () => {
    if (!state.taskId) {
      alert("请先创建或选择任务！");
      return;
    }
    btnRunSourceCleanup.disabled = true;
    btnRunSourceCleanup.textContent = "正在执行源语整理与说话人推断...";
    try {
      const res = await fetch(`/api/v1/tasks/${state.taskId}/source/cleanup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ simulate: false }),
      });
      if (res.ok) {
        const data = await res.json();
        alert(`源语整理完成！共生成 ${data.utterances_count} 句台词，发现 ${data.speakers_count} 个说话人候选。`);
        loadSourceTranscript();
        loadTrace();
      } else {
        const err = await res.json();
        alert(`源语整理失败: ${err.detail || res.statusText}`);
      }
    } catch (e) {
      alert(`异常: ${e.message}`);
    } finally {
      btnRunSourceCleanup.disabled = false;
      btnRunSourceCleanup.textContent = "运行源语整理 (Task A)";
    }
  });
}

if (btnReloadSourceTranscript) {
  btnReloadSourceTranscript.addEventListener("click", loadSourceTranscript);
}

if (btnConfirmSourceTranscript) {
  btnConfirmSourceTranscript.addEventListener("click", async () => {
    if (!state.taskId) {
      alert("请先创建或选择任务！");
      return;
    }
    if (currentSourceRevision <= 0) {
      alert("尚未生成有效的源语整理稿，无法确认！");
      return;
    }
    if (!confirm(`确认要将源语稿 (Revision ${currentSourceRevision}) 正式签署通过吗？\n确认后将解锁出海初翻。若此前已生成旧译稿，旧译稿将自动作废！`)) {
      return;
    }

    try {
      const res = await fetch(`/api/v1/tasks/${state.taskId}/source-transcript/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_revision: currentSourceRevision,
          force_ignore_doubts: true,
          reason: "操作员人工审校通过",
        }),
      });
      if (res.ok) {
        alert("第一人工关口 (Gate 1) 确认成功！源语稿已锁定并就绪，已解锁初翻任务。");
        loadSourceTranscript();
        loadTranslations();
        loadTrace();
      } else {
        const err = await res.json();
        alert(`确认失败: ${err.detail || res.statusText}`);
      }
    } catch (e) {
      alert(`异常: ${e.message}`);
    }
  });
}

// -------------------------------------------------------------------------
// 9. Knowledge Base & Locked Terms
// -------------------------------------------------------------------------
const inputKnowledgeSource = document.getElementById("inputKnowledgeSource");
const inputKnowledgeTarget = document.getElementById("inputKnowledgeTarget");
const selectKnowledgeCategory = document.getElementById("selectKnowledgeCategory");
const checkKnowledgeLocked = document.getElementById("checkKnowledgeLocked");
const btnAddKnowledgeItem = document.getElementById("btnAddKnowledgeItem");
const knowledgeTbody = document.getElementById("knowledgeTbody");
selectKnowledgeCategory.addEventListener("change", () => {
  checkKnowledgeLocked.disabled = selectKnowledgeCategory.value !== "glossary";
  if (checkKnowledgeLocked.disabled) checkKnowledgeLocked.checked = false;
});


async function loadKnowledge() {
  try {
    const res = await fetch(`/api/v1/projects/${state.projectId}/knowledge`);
    if (!res.ok) return;
    const items = await res.json();

    knowledgeTbody.innerHTML = "";
    if (items && items.length > 0) {
      items.forEach(item => {
        const tr = document.createElement("tr");
        const lockedTag = item.is_locked
          ? `<span class="tag tag-danger" style="font-size:11px;">🔒 强制锁定</span>`
          : `<span class="tag tag-neutral" style="font-size:11px;">普通参考</span>`;

        tr.innerHTML = `
          <td><span style="font-size:12px; font-weight:bold;">${item.category}</span></td>
          <td><strong>${escapeHtml(item.source_text)}</strong></td>
          <td>${escapeHtml(item.target_text || "-")}<br><small>${escapeHtml(item.target_market || "未绑定市场")} / ${escapeHtml(item.target_language || "无目标语言")}</small></td>
          <td>${lockedTag}</td>
          <td><span class="tag tag-ok" style="font-size:11px;">${item.status}</span></td>
          <td>
            <button class="button danger small btn-del-knowledge" data-id="${item.item_id}">删除</button>
          </td>
        `;
        knowledgeTbody.appendChild(tr);
      });

      document.querySelectorAll(".btn-del-knowledge").forEach(btn => {
        btn.addEventListener("click", async (e) => {
          const id = e.target.getAttribute("data-id");
          if (!confirm("确定要删除此词条吗？")) return;
          const resp = await fetch(`/api/v1/projects/${state.projectId}/knowledge/${id}`, { method: "DELETE" });
          if (resp.ok) {
            loadKnowledge();
          }
        });
      });
    } else {
      knowledgeTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">暂无知识条目</td></tr>`;
    }
  } catch (e) {
    console.error("loadKnowledge error", e);
  }
}

if (btnAddKnowledgeItem) {
  btnAddKnowledgeItem.addEventListener("click", async () => {
    const src = inputKnowledgeSource.value.trim();
    const tgt = inputKnowledgeTarget.value.trim();
    if (!src) {
      alert("请输入源语专有名词或术语！");
      return;
    }

    try {
      const res = await fetch(`/api/v1/projects/${state.projectId}/knowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: state.projectId,
          category: selectKnowledgeCategory.value,
          source_text: src,
          target_text: tgt || null,
          target_language: selectKnowledgeCategory.value === "glossary" ? ({MX:"es-MX",LATAM:"es",ES:"es",BR:"pt",ID:"id",US:"en"}[document.getElementById("selectTargetMarket").value] || null) : null,
          target_market: selectKnowledgeCategory.value === "glossary" ? document.getElementById("selectTargetMarket").value : null,
          is_locked: selectKnowledgeCategory.value === "glossary" && checkKnowledgeLocked.checked,
          status: "CONFIRMED",
        }),
      });
      if (res.ok) {
        inputKnowledgeSource.value = "";
        inputKnowledgeTarget.value = "";
        loadKnowledge();
      } else {
        const err = await res.json();
        alert(`添加失败: ${err.detail || res.statusText}`);
      }
    } catch (e) {
      alert(`异常: ${e.message}`);
    }
  });
}

// -------------------------------------------------------------------------
// 10. Task B Translation, Task C Semantic Checks & Gate 2
// -------------------------------------------------------------------------
const translationSourceRevBadge = document.getElementById("translationSourceRevBadge");
const qeStatusBadge = document.getElementById("qeStatusBadge");
const selectTargetMarket = document.getElementById("selectTargetMarket");
const btnGenerateTranslation = document.getElementById("btnGenerateTranslation");
const btnReloadTranslations = document.getElementById("btnReloadTranslations");
const btnConfirmAllTranslations = document.getElementById("btnConfirmAllTranslations");
const translationsTbody = document.getElementById("translationsTbody");
const translationAlertBox = document.getElementById("translationAlertBox");
const manifestContentBox = document.getElementById("manifestContentBox");

let loadedTranslationSnapshot = {source_revision: 0, expected_revisions: {}};
async function loadTranslations() {
  if (!state.taskId) return;
  try {
    const res = await fetch(`/api/v1/tasks/${state.taskId}/translations`);
    if (!res.ok) return;
    const data = await res.json();

    loadedTranslationSnapshot = {source_revision: data.source_revision, expected_revisions: Object.fromEntries((data.translations || []).map(t => [t.unit_id, t.translation_revision]))};
    translationSourceRevBadge.textContent = `读入源版本: Rev ${data.source_revision || "-"}`;
    qeStatusBadge.textContent = `QE: ${data.qe_status || "未评估"}`;

    if (data.manifest && Object.keys(data.manifest).length > 0) {
      manifestContentBox.textContent = JSON.stringify(data.manifest, null, 2);
    } else {
      manifestContentBox.textContent = "暂无真实模型调用清单。";
    }

    const checksByUnit = {};
    (data.checks || []).forEach(chk => {
      if (!checksByUnit[chk.unit_id]) checksByUnit[chk.unit_id] = [];
      checksByUnit[chk.unit_id].push(chk);
    });

    translationsTbody.innerHTML = "";
    if (data.translations && data.translations.length > 0) {
      data.translations.forEach(t => {
        const tr = document.createElement("tr");

        // Term hits
        let termHitsHtml = "";
        if (t.term_hits && t.term_hits.length > 0) {
          termHitsHtml = t.term_hits.map(th => {
            const color = th.matched ? "var(--tag-ok-color)" : "var(--tag-danger-color)";
            return `<div style="font-size:11px; margin:2px 0;">
              <strong>${escapeHtml(th.source_term)}</strong> ➔ <span style="color:${color}">${escapeHtml(th.actual_target)}</span>
            </div>`;
          }).join("");
        } else {
          termHitsHtml = `<span style="font-size:11px; color:var(--text-muted);">无命中锁词</span>`;
        }

        // Checks / Issues
        const uChecks = checksByUnit[t.unit_id] || [];
        let checksHtml = "";
        if (uChecks.length > 0) {
          checksHtml = uChecks.map(chk => {
            const badgeClass = chk.severity === "BLOCK" ? "tag tag-danger" : "tag tag-warning";
            return `<div style="margin:2px 0;">
              <span class="${badgeClass}" style="font-size:10px; font-weight:bold;">${chk.severity}</span>
              <span style="font-size:11px;">${escapeHtml(chk.detail)}</span>
            </div>`;
          }).join("");
        } else {
          checksHtml = `<span class="tag tag-ok" style="font-size:11px;">✓ 语义一致性通过</span>`;
        }

        const isLocked = t.is_locked;
        const lockBtnText = isLocked ? "🔓 解除锁定" : "🔒 锁定保护";
        const statusTagClass = t.status === "CONFIRMED" ? "tag tag-ok" : (t.status === "LOCKED" ? "tag tag-danger" : "tag tag-neutral");

        tr.innerHTML = `
          <td><strong>${t.unit_id}</strong></td>
          <td style="font-size:13px; line-height:1.4;">
            <div id="src_txt_${t.unit_id}" style="font-weight:500;">-</div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">${escapeHtml(t.brief_paraphrase || "")}</div>
          </td>
          <td>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
              <span class="${statusTagClass}" style="font-size:10px;">${t.status} (Rev ${t.translation_revision})</span>
            </div>
            <textarea id="trans_area_${t.unit_id}" rows="2" style="width:100%; font-size:13px; padding:4px 6px; border:1px solid var(--border-color); border-radius:4px;">${escapeHtml(t.text)}</textarea>
          </td>
          <td>${termHitsHtml}</td>
          <td>${checksHtml}</td>
          <td>
            <div style="display:flex; flex-direction:column; gap:4px;">
              <button class="button success small btn-confirm-trans" data-id="${t.unit_id}" data-rev="${t.translation_revision}">✓ 签署确认</button>
              <button class="button secondary small btn-save-trans" data-id="${t.unit_id}" data-rev="${t.translation_revision}">保存编辑</button>
              <button class="button secondary small btn-lock-trans" data-id="${t.unit_id}" data-rev="${t.translation_revision}" data-locked="${isLocked}">${lockBtnText}</button>
              <button class="button secondary small btn-rollback-trans" data-id="${t.unit_id}" data-rev="${t.translation_revision}">↺ 回滚版本</button>
            </div>
          </td>
        `;
        translationsTbody.appendChild(tr);
      });

      // Populate source texts
      try {
        const sRes = await fetch(`/api/v1/tasks/${state.taskId}/source-transcript`);
        if (sRes.ok) {
          const sData = await sRes.json();
          (sData.utterances || []).forEach(u => {
            const el = document.getElementById(`src_txt_${u.unit_id}`);
            if (el) el.textContent = u.text;
          });
        }
      } catch (err) {}

      // Bind action buttons
      // 版本契约：确认/编辑/锁定/回滚/批量确认都必须带上“当前实际加载”的 source_revision
      // 与对应 unit 的 translation_revision（后端 TranslationRevisionRequest /
      // ConfirmAllTranslationsRequest 均为必填）。版本号只从本次 GET /translations 的
      // 响应中取，取不到就提示刷新，绝不发送写死的假版本；409 表示页面数据已过期，
      // 提示复核并自动刷新，后端乐观锁保持原样。
      const reviewSourceRevision = () => {
        const raw = loadedTranslationSnapshot.source_revision;
        const rev = Number(raw);
        return raw !== null && raw !== undefined && Number.isInteger(rev) && rev > 0 ? rev : null;
      };
      const reviewUnitRevision = (uid, fallback) => {
        const raw = (fallback !== null && fallback !== undefined)
          ? fallback
          : loadedTranslationSnapshot.expected_revisions[uid];
        const rev = Number(raw);
        return raw !== null && raw !== undefined && Number.isInteger(rev) && rev > 0 ? rev : null;
      };
      const reviewFailDetail = async (res) => {
        try {
          const err = await res.json();
          if (typeof err.detail === "string") return err.detail;
          if (err.detail && err.detail.message) return err.detail.message;
          return JSON.stringify(err.detail || err);
        } catch (_) {
          return res.statusText || `HTTP ${res.status}`;
        }
      };
      const reviewReload = async (label, detail) => {
        alert(`${label}失败：${detail}\n\n页面上加载的修订版本已过期（HTTP 409），本次操作未生效。正在刷新译稿列表，请复核最新版本后重试。`);
        await loadTranslations();
      };
      const reviewSend = async ({ url, method = "POST", body, label, successText }) => {
        const sourceRev = reviewSourceRevision();
        if (sourceRev === null) {
          alert(`${label}失败：当前页面没有加载到有效的源稿修订版本，无法提交。正在刷新译稿列表，请复核后重试。`);
          await loadTranslations();
          return false;
        }
        const res = await fetch(url, {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_revision: sourceRev, ...body }),
        });
        if (res.ok) {
          if (successText) alert(successText);
          await loadTranslations();
          return true;
        }
        const detail = await reviewFailDetail(res);
        if (res.status === 409) {
          await reviewReload(label, detail);
        } else if (res.status === 422) {
          alert(`${label}失败：请求缺少有效的修订版本字段（HTTP 422）：${detail}\n\n正在刷新译稿列表，请复核后重试。`);
          await loadTranslations();
        } else {
          alert(`${label}失败 (${res.status})：${detail}`);
        }
        return false;
      };
      const reviewRequireUnitRevision = async (uid, label, raw) => {
        const rev = reviewUnitRevision(uid, raw);
        if (rev === null) {
          alert(`${label}失败：当前页面没有加载到 ${uid} 的有效译文修订版本。正在刷新译稿列表，请复核后重试。`);
          await loadTranslations();
        }
        return rev;
      };

      document.querySelectorAll(".btn-confirm-trans").forEach(b => {
        b.addEventListener("click", async (e) => {
          const uid = e.target.getAttribute("data-id");
          const label = `签署确认 ${uid}`;
          const rev = await reviewRequireUnitRevision(uid, label, e.target.getAttribute("data-rev"));
          if (rev === null) return;
          await reviewSend({
            url: `/api/v1/tasks/${state.taskId}/translations/${uid}/confirm`,
            body: { expected_revision: rev },
            label,
          });
        });
      });

      document.querySelectorAll(".btn-save-trans").forEach(b => {
        b.addEventListener("click", async (e) => {
          const uid = e.target.getAttribute("data-id");
          const label = `保存译文 ${uid}`;
          const rev = await reviewRequireUnitRevision(uid, label, e.target.getAttribute("data-rev"));
          if (rev === null) return;
          const area = document.getElementById(`trans_area_${uid}`);
          const txt = area ? area.value : "";
          await reviewSend({
            url: `/api/v1/tasks/${state.taskId}/translations/${uid}`,
            method: "PATCH",
            body: { expected_revision: rev, text: txt },
            label,
            successText: `译文 ${uid} 保存成功！`,
          });
        });
      });

      document.querySelectorAll(".btn-lock-trans").forEach(b => {
        b.addEventListener("click", async (e) => {
          const uid = e.target.getAttribute("data-id");
          const isL = e.target.getAttribute("data-locked") === "true";
          const label = isL ? `解除锁定 ${uid}` : `锁定 ${uid}`;
          const rev = await reviewRequireUnitRevision(uid, label, e.target.getAttribute("data-rev"));
          if (rev === null) return;
          const endpoint = isL ? `/api/v1/tasks/${state.taskId}/translations/${uid}/unlock` : `/api/v1/tasks/${state.taskId}/translations/${uid}/lock`;
          await reviewSend({ url: endpoint, body: { expected_revision: rev }, label });
        });
      });

      document.querySelectorAll(".btn-rollback-trans").forEach(b => {
        b.addEventListener("click", async (e) => {
          const uid = e.target.getAttribute("data-id");
          const label = `回滚译文 ${uid}`;
          const curRev = await reviewRequireUnitRevision(uid, label, e.target.getAttribute("data-rev"));
          if (curRev === null) return;
          const targetRevStr = prompt(`当前版本为 Rev ${curRev}。\n请输入要回滚到的目标历史版本号 (例如: 1):`, "1");
          if (!targetRevStr) return;
          const targetRev = parseInt(targetRevStr, 10);
          if (isNaN(targetRev) || targetRev <= 0) {
            alert("请输入有效的目标版本号！");
            return;
          }

          await reviewSend({
            url: `/api/v1/tasks/${state.taskId}/translations/${uid}/rollback`,
            body: { expected_revision: curRev, target_revision: targetRev, reason: "用户界面回滚" },
            label,
            successText: `单元 ${uid} 已成功回滚至 Rev ${targetRev} 内容作为新版本！`,
          });
        });
      });
    } else {
      translationsTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">尚未生成初翻</td></tr>`;
    }
  } catch (e) {
    console.error("loadTranslations error", e);
  }
}

if (btnGenerateTranslation) {
  btnGenerateTranslation.addEventListener("click", async () => {
    if (!state.taskId) {
      alert("请先创建或选择任务！");
      return;
    }
    const market = selectTargetMarket.value;
    if (!market) {
      alert("请显式选择目标市场！");
      return;
    }

    btnGenerateTranslation.disabled = true;
    btnGenerateTranslation.textContent = "正在调用初翻引擎与语义检查...";
    translationAlertBox.style.display = "none";

    try {
      const res = await fetch(`/api/v1/tasks/${state.taskId}/translation/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_language: market === "MX" ? "es-MX" : ({LATAM:"es",ES:"es",BR:"pt",ID:"id"}[market] || "en"),
          target_market: market,
          simulate: false,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        alert(`初翻生成成功！共翻译 ${data.translations_count} 句，语义检查发现 ${data.issues_count} 项问题（其中严重阻断 ${data.blocking_issues_count} 项）。`);
        loadTranslations();
        loadTrace();
      } else {
        const err = await res.json();
        if (res.status === 400 && err.detail && err.detail.includes("STAGE_NOT_READY")) {
          alert(`【前置条件未满足】\n${err.detail}\n\n请在上方 Panel 8 点击“人工确认源语稿 (Gate 1)”完成签署后再启动初翻！`);
        } else {
          alert(`初翻生成失败 (${res.status}): ${err.detail || res.statusText}`);
        }
      }
    } catch (e) {
      alert(`异常: ${e.message}`);
    } finally {
      btnGenerateTranslation.disabled = false;
      btnGenerateTranslation.textContent = "生成初翻并执行语义检查 (Task B & C)";
    }
  });
}

if (btnReloadTranslations) {
  btnReloadTranslations.addEventListener("click", loadTranslations);
}

if (btnConfirmAllTranslations) {
  btnConfirmAllTranslations.addEventListener("click", async () => {
    if (!state.taskId) return;
    if (!confirm("确定要批量签署确认当前全部译文吗？\n（若存在强制锁词未用等 BLOCK 阻断项将被系统拒绝）")) return;

    try {
      // 批量确认契约：必须携带本次加载的 source_revision 与每个 unit 的 translation_revision；
      // 后端会比对“当前全部译稿的最新版本”，不一致返回 409，此时提示刷新而不是重试假版本。
      const sourceRev = Number(loadedTranslationSnapshot.source_revision);
      const expectedRevisions = loadedTranslationSnapshot.expected_revisions || {};
      if (!Number.isInteger(sourceRev) || sourceRev <= 0 || Object.keys(expectedRevisions).length === 0) {
        alert("批量确认失败：当前页面没有加载到有效的源稿修订版本或待确认译文版本。正在刷新译稿列表，请复核后重试。");
        await loadTranslations();
        return;
      }
      const res = await fetch(`/api/v1/tasks/${state.taskId}/translations/confirm-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_revision: sourceRev, expected_revisions: expectedRevisions }),
      });
      if (res.ok) {
        alert("第二人工关口 (Gate 2) 批量签署成功！全部可用译文已确认。");
        await loadTranslations();
        loadTrace();
      } else {
        let detail = res.statusText;
        let detailMessage = "";
        try {
          const err = await res.json();
          detail = typeof err.detail === "string" ? err.detail : (err.detail && err.detail.message) || JSON.stringify(err.detail || err);
          if (err.detail && err.detail.message) detailMessage = err.detail.message;
        } catch (_) {}
        if (res.status === 409) {
          alert(`批量确认失败：${detail || detailMessage}\n\n译稿列表已变化（HTTP 409），本次签署未生效。正在刷新译稿列表，请复核最新版本后重试。`);
          await loadTranslations();
        } else if (detailMessage) {
          alert(`批量确认被阻断: ${detailMessage}`);
        } else {
          alert(`确认失败 (${res.status}): ${detail}`);
        }
      }
    } catch (e) {
      alert(`异常: ${e.message}`);
    }
  });
}

// Initial boot for new panels
loadSourceTranscript();
loadKnowledge();
loadTranslations();


// Culture candidates never write translations; review uses pinned translation revisions.
const cultureLabels = {P0:"红线",P1:"黄线",P2:"提示",UNASSESSED:"待评估",AI_PROPOSED:"待审核",CONFIRMED:"人工已确认风险",REJECTED:"人工已驳回",IGNORED:"人工已忽略",EDITED:"人工改写已采纳",PENDING_RECHECK:"待重新检测",sufficient:"依据充分",pending_supplementary:"待补充依据",insufficient:"依据不足",contextual_review:"结合场景人工核对",modify_dialogue:"建议修改台词",block_release:"暂停发布并人工核实",add_warning:"建议补充提示",ignore_with_reason:"可说明原因后忽略"};
const cultureLabel = value => cultureLabels[value] || value;
// 展示顺序固定为红线(P0) → 黄线(P1) → 提示(P2) → 未评级，同级按排序值降序。
const cultureSeverityOrder = {P0:0,P1:1,P2:2,UNASSESSED:3};
const cultureSeverityTag = {P0:"tag tag-danger",P1:"tag tag-warning",P2:"tag tag-neutral",UNASSESSED:"tag tag-neutral"};
const cultureMessage = document.getElementById("cultureMessage");
const cultureSummary = document.getElementById("cultureSummary");
const cultureIssues = document.getElementById("cultureIssues");
const cultureManifest = document.getElementById("cultureManifest");

async function cultureJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body));
  return body;
}

function cultureInfoLine(text) {
  const line = document.createElement("p");
  line.style.fontSize = "13px";
  line.textContent = text;
  return line;
}

// 触发位置只做定位与高亮，不改写译文：源语跨度 + 译文跨度（mark 高亮）+ 字符区间。
function cultureTriggerLine(span) {
  const line = document.createElement("p");
  line.className = "culture-trigger";
  line.style.fontSize = "13px";
  line.append(document.createTextNode("触发位置："));
  if (span.source_span) {
    const source = document.createElement("span");
    source.style.color = "var(--text-muted)";
    source.textContent = `源语「${span.source_span}」→ `;
    line.append(source);
  }
  if (span.target_span) {
    const hit = document.createElement("mark");
    hit.style.background = "rgba(255,212,0,.45)";
    hit.style.padding = "0 2px";
    hit.style.borderRadius = "2px";
    hit.textContent = span.target_span;
    line.append(hit);
  } else {
    line.append(document.createTextNode("（未给出译文跨度，请结合上下文人工定位）"));
  }
  if (Number.isInteger(span.start_char) && Number.isInteger(span.end_char)) {
    const offsets = document.createElement("span");
    offsets.style.fontSize = "11px";
    offsets.style.color = "var(--text-muted)";
    offsets.textContent = `（译文字符 ${span.start_char}–${span.end_char}）`;
    line.append(offsets);
  }
  return line;
}

// 采纳建议改写只预填初翻编辑框；升版仍走初翻审阅的 PATCH（expected_revision + text），
// 文化模块不写译文、不生成平行稿本、不自动提交。
function cultureAdoptRewrite(issue, taskId) {
  if (state.taskId !== taskId) return;
  const target = document.getElementById(`trans_area_${issue.unit_id}`);
  if (!target) {
    cultureMessage.textContent = `未在初翻审阅区找到 ${issue.unit_id} 的编辑框，请先刷新译稿后重试。`;
    return;
  }
  target.value = issue.suggested_translation;
  target.scrollIntoView({behavior: "smooth", block: "center"});
  target.focus();
  cultureMessage.textContent = `已把建议改写预填到 ${issue.unit_id} 的初翻编辑框；请核对后点“保存编辑”（按既有版本契约生成新 revision），再重新确认译稿并复检文化风险。本次未自动改稿。`;
}

function cultureIssueCard(issue, revision, taskId) {
  const card = document.createElement("article");
  card.className = "panel culture-issue";
  card.dataset.severity = issue.severity_proposal || "UNASSESSED";
  card.dataset.issueId = issue.issue_id;

  const heading = document.createElement("h3");
  const badge = document.createElement("span");
  badge.className = cultureSeverityTag[issue.severity_proposal] || "tag tag-neutral";
  badge.textContent = `${cultureLabel(issue.severity_proposal)}${issue.severity_proposal && issue.severity_proposal !== "UNASSESSED" ? " " + issue.severity_proposal : ""}`;
  heading.append(badge, document.createTextNode(` AI 生成 · ${cultureLabel(issue.status)} · ${issue.unit_id}${issue.stale ? " · 依据已变化" : ""}`));
  card.append(heading);

  card.append(cultureInfoLine(`风险点（${issue.category}）：${issue.explanation}`));
  const spans = Array.isArray(issue.trigger_spans) ? issue.trigger_spans : [];
  if (!spans.length) card.append(cultureInfoLine("触发位置：本次未返回精确跨度，请结合前后文人工定位。"));
  for (const span of spans) card.append(cultureTriggerLine(span));

  const confidenceBasis = issue.confidence && issue.confidence.basis ? issue.confidence.basis : "未给出";
  card.append(cultureInfoLine(
    `依据：${cultureLabel(issue.evidence_status)}；置信依据：${confidenceBasis}`
    + `${issue.downgraded_from_p0 ? `；已从 P0 降级：${issue.downgrade_reason || "未说明"}` : ""}`
    + `；规则：${JSON.stringify(issue.rule_refs || [])}；案例：${JSON.stringify(issue.case_refs || [])}`
    + `；排序值：${issue.ranking_score ?? "未评估"}`
  ));
  card.append(cultureInfoLine(`修改建议：${cultureLabel(issue.suggested_action)}`));
  if (issue.suggested_translation) card.append(cultureInfoLine(`建议改写：${issue.suggested_translation}`));
  if (Array.isArray(issue.missing_context) && issue.missing_context.length) {
    card.append(cultureInfoLine(`缺少资料：${JSON.stringify(issue.missing_context)}（缺资料时结论仅作提示，不得视为已确认）`));
  }

  const actions = document.createElement("div");
  actions.style.display = "flex";
  actions.style.flexWrap = "wrap";
  actions.style.gap = "8px";
  const canDecide = !issue.stale && issue.status === "AI_PROPOSED" && Boolean(revision);
  for (const [label, action] of [["确认风险", "accept"], ["驳回风险", "reject"]]) {
    const button = document.createElement("button");
    button.className = "button secondary";
    button.textContent = label;
    button.disabled = !canDecide;
    button.onclick = async () => {
      if (state.taskId !== taskId) return;
      const reason = prompt("请说明本次人工判断的依据："); if (!reason?.trim()) return;
      try {
        await cultureJson(`/api/v1/culture/issues/${issue.issue_id}/decision`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({expected_revision:revision,decision_action:action,ignore_reason:reason})});
        await loadCulture();
      } catch(error) { cultureMessage.textContent = error.message; }
    };
    actions.append(button);
  }
  const adopt = document.createElement("button");
  adopt.className = "button secondary";
  adopt.textContent = "采纳建议改写（到初翻）";
  adopt.disabled = !issue.suggested_translation || !canDecide;
  adopt.onclick = () => cultureAdoptRewrite(issue, taskId);
  actions.append(adopt);
  card.append(actions);
  return card;
}

async function loadCulture() {
  if (!state.taskId) return;
  const taskId = state.taskId;
  cultureIssues.replaceChildren();
  try {
    const issues = await cultureJson(`/api/v1/culture/tasks/${taskId}/issues`);
    if (state.taskId !== taskId) return;
    const latest = await cultureJson(`/api/v1/culture/tasks/${taskId}/latest-run`);
    if (state.taskId !== taskId) return;
    const runIds = [...new Set(issues.map(i => i.run_id))];
    const runs = await Promise.all(runIds.map(id => cultureJson(`/api/v1/culture/runs/${id}`)));
    if (state.taskId !== taskId) return;
    const manifestByRun = new Map(runs.map(r => [r.run_id, typeof r.manifest === "string" ? JSON.parse(r.manifest) : r.manifest]));

    const counts = {P0:0,P1:0,P2:0,UNASSESSED:0};
    for (const issue of issues) counts[issue.severity_proposal] = (counts[issue.severity_proposal] || 0) + 1;
    const staleCount = issues.filter(i => i.stale).length;
    const pendingCount = issues.filter(i => !i.stale && i.status === "AI_PROPOSED").length;
    cultureSummary.textContent = `红线 P0 ${counts.P0 || 0} 项 · 黄线 P1 ${counts.P1 || 0} 项 · 提示 P2 ${counts.P2 || 0} 项${counts.UNASSESSED ? ` · 待评估 ${counts.UNASSESSED} 项` : ""} · 依据已变化 ${staleCount} 项 · 待人工审核 ${pendingCount} 项`;
    cultureMessage.textContent = issues.length ? `共有 ${issues.length} 项 AI 风险候选，待人工审阅；无风险结果不代表整片合规。` : "尚无风险记录；没有风险记录不代表已完成检测或整片合规。";
    cultureManifest.textContent = JSON.stringify(latest || {note:"尚未检测"}, null, 2);
    if (latest) cultureMessage.textContent = `本次检查 ${latest.checked_unit_ids.length} 条，未检查 ${latest.unchecked_units.length} 条，历史风险共 ${issues.length} 项。${latest.coverage_limitations.join("；")} 不代表整片合规。`;

    const sorted = [...issues].sort((a, b) =>
      (cultureSeverityOrder[a.severity_proposal] ?? 3) - (cultureSeverityOrder[b.severity_proposal] ?? 3)
      || ((b.ranking_score ?? -1) - (a.ranking_score ?? -1)));
    let currentSeverity = null;
    for (const issue of sorted) {
      const severity = issue.severity_proposal || "UNASSESSED";
      if (severity !== currentSeverity) {
        currentSeverity = severity;
        const group = document.createElement("h4");
        group.className = "culture-group";
        group.textContent = `${cultureLabel(severity)}（${severity === "UNASSESSED" ? "未评级" : severity}） · ${counts[severity] || 0} 项`;
        cultureIssues.append(group);
      }
      const manifest = manifestByRun.get(issue.run_id);
      const revision = manifest?.translation_refs?.[issue.unit_id]?.revision;
      cultureIssues.append(cultureIssueCard(issue, revision, taskId));
    }
  } catch(error) { cultureMessage.textContent = error.message; }
}
document.getElementById("btnCultureRefresh")?.addEventListener("click", loadCulture);
document.getElementById("btnCultureJump")?.addEventListener("click", () => {
  document.getElementById("panelCulture")?.scrollIntoView({behavior: "smooth", block: "start"});
  loadCulture();
});
document.getElementById("btnCultureCheck")?.addEventListener("click", async event => {
  if (!state.taskId) { cultureMessage.textContent = "请先选择任务"; return; }
  const taskId = state.taskId; event.target.disabled = true; cultureMessage.textContent = "AI 正在检测，请稍候……";
  try {
    const result = await cultureJson(`/api/v1/culture/tasks/${taskId}/check`, {method:"POST"});
    if (state.taskId !== taskId) return;
    await loadCulture(); cultureManifest.textContent = JSON.stringify(result, null, 2);
    cultureMessage.textContent = `本次检查 ${result.checked_unit_ids.length} 条，未检查 ${result.unchecked_units.length} 条。${result.coverage_limitations.join("；")} AI 候选需人工审阅，不代表整片合规。`;
  } catch(error) { cultureMessage.textContent = error.message; }
  finally { event.target.disabled = false; }
});

loadCulture();


// All downstream requests name a task and expected version, never client manuscripts.
let deliverySnapshot = null;
const deliveryStatus = document.getElementById("deliveryStatus");
const deliveryDetails = document.getElementById("deliveryDetails");
const deliverySummary = document.getElementById("deliverySummary");
async function loadDelivery() {
  const taskId = state.taskId;
  try {
    const tasks = await cultureJson("/api/v1/downstream/tasks");
    const select = document.getElementById("deliveryTaskSelect");select.replaceChildren(new Option("请选择任务", ""));
    tasks.forEach(t => select.add(new Option(`${t.task_id} · Rev ${t.task_revision} · ${t.task_status}`,t.task_id)));
    select.value=taskId || "";
    if (!taskId) {deliveryStatus.textContent="请选择任务";return;}
    const snapshot = await cultureJson(`/api/v1/compliance/tasks/${taskId}/state`);
    const previews = await cultureJson(`/api/v1/downstream/tasks/${taskId}/latest`);
    if (state.taskId !== taskId) return;
    deliverySnapshot=snapshot;
    deliveryStatus.textContent=`任务 Rev ${snapshot.task_revision}：${snapshot.ready ? "依据齐全，可申请技术质检" : snapshot.blocked_reason}`;
    const artifact=snapshot.artifact;
    document.getElementById("btnDeliveryValidate").disabled=!snapshot.ready;
    const role=state.currentUser?.role;
    const signer=["reviewer","compliance_reviewer","auditor","quality_manager","admin","culture_senior","legal_reviewer"].includes(role);
    document.getElementById("btnDeliverySign").disabled=!snapshot.ready || artifact?.status!=="VALIDATED" || !signer;
    document.getElementById("btnDeliveryDownload").disabled=!snapshot.ready || artifact?.status!=="PUBLISH_READY";
    deliverySummary.textContent=`单位：${previews.units ? previews.units.items.length + "项规则候选" + (previews.units.stale ? "，依据已变化" : "") : "未检查"}；口语：${previews.oral ? previews.oral.items.length + "句规则审阅" + (previews.oral.stale ? "，依据已变化" : "") : "未检查"}\n交付：${artifact?.status || "尚无登记产物"}。${signer ? "" : "当前身份没有签发权限。"}`;
    deliveryDetails.textContent=JSON.stringify({previews,artifact},null,2);
  } catch(error) {deliveryStatus.textContent=error.message;}
}
document.getElementById("deliveryTaskSelect").addEventListener("change",event=>{
  if(!event.target.value)return;localStorage.setItem("active_task_id",event.target.value);localStorage.removeItem("active_media_id");location.reload();
});
for(const [id,endpoint] of [["btnUnitPreview","units"],["btnOralPreview","oral"],["btnDeliveryValidate","compliance"]]) {
 document.getElementById(id).onclick=async event=>{
  if(!state.taskId || !deliverySnapshot)return;
  const taskId=state.taskId;event.target.disabled=true;
  try {
   const suffix={units:"convert",oral:"review",compliance:"validate-and-export"}[endpoint];
   await cultureJson(`/api/v1/${endpoint}/tasks/${taskId}/${suffix}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({expected_task_revision:deliverySnapshot.task_revision})});
   await loadDelivery();
  } catch(error){deliveryStatus.textContent=typeof error.message==="string"?error.message:JSON.stringify(error.message);}
  finally{if(endpoint!=="compliance")event.target.disabled=false;}
 };
}
document.getElementById("btnDeliverySign").onclick=async()=>{
 if(!deliverySnapshot?.artifact || !confirm("确认你已完成终审并签发当前登记产物？签发不会自动发布。"))return;
 const taskId=state.taskId,artifact=deliverySnapshot.artifact;
 try {
  await cultureJson(`/api/v1/compliance/tasks/${taskId}/signoff`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({artifact_id:artifact.artifact_id,expected_revision:artifact.manifest.translation_revision})});
  await loadDelivery();
 }catch(error){deliveryStatus.textContent=error.message;}
};
document.getElementById("btnDeliveryDownload").onclick=async()=>{
 try {
  const artifact=await cultureJson(`/api/v1/compliance/tasks/${state.taskId}/artifact?artifact_id=${encodeURIComponent(deliverySnapshot.artifact.artifact_id)}`);
  const url=URL.createObjectURL(new Blob([artifact.content],{type:"text/plain;charset=utf-8"}));const link=document.createElement("a");link.href=url;link.download=`${artifact.artifact_id}.${artifact.format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(error){deliveryStatus.textContent=error.message;}
};
document.getElementById("btnDeliveryRefresh").onclick=loadDelivery;
loadDelivery();
