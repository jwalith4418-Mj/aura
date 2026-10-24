import * as api from './api.js';

const state = {
  sessionId: null,
  domain: null,
  loopStage: 0,
  diagnosticQuestion: null,
  targetConcept: null,
  entropyBefore: 0,
};

const dsaEvidencePool = [
  {
    "timestamp": "2026-08-17T22:10:00+05:30",
    "concept": "binary_search",
    "secondary_concepts": ["boundary_handling"],
    "test_results": {"passed": ["normal_asc", "normal_desc"], "failed": ["left_boundary", "single_element"]},
    "failure_classes": ["left_boundary", "single_element"],
    "static_pattern": "low_mid_no_increment",
    "recurrence": true,
    "code": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low < high:\n        mid = (low + high) // 2\n        if arr[mid] < target:\n            low = mid\n        else:\n            high = mid\n    return low if arr[low] == target else -1"
  },
  {
    "timestamp": "2026-08-17T22:15:00+05:30",
    "concept": "binary_search",
    "secondary_concepts": ["boundary_handling"],
    "test_results": {"passed": ["normal_asc", "duplicate_values"], "failed": ["left_boundary", "right_boundary"]},
    "failure_classes": ["left_boundary", "right_boundary"],
    "static_pattern": "off_by_one_bound",
    "recurrence": false,
    "code": "def binary_search(arr, target):\n    low, high = 0, len(arr)\n    while low < high:\n        mid = (low + high) // 2\n        if arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return low"
  },
  {
    "timestamp": "2026-08-17T22:20:00+05:30",
    "concept": "binary_search",
    "secondary_concepts": ["loop_invariant"],
    "test_results": {"passed": [], "failed": ["normal_asc", "single_element", "left_boundary"]},
    "failure_classes": ["loop_never_terminates"],
    "static_pattern": "loop_never_terminates",
    "recurrence": true,
    "code": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid\n        else:\n            high = mid"
  },
  {
    "timestamp": "2026-08-17T22:25:00+05:30",
    "concept": "boundary_handling",
    "secondary_concepts": ["binary_search"],
    "test_results": {"passed": ["normal_desc"], "failed": ["duplicate_values", "single_element"]},
    "failure_classes": ["high_mid_no_decrement"],
    "static_pattern": "high_mid_no_decrement",
    "recurrence": true,
    "code": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low < high:\n        mid = (low + high) // 2\n        if arr[mid] <= target:\n            low = mid\n        else:\n            high = mid - 1\n    return low"
  },
  {
    "timestamp": "2026-08-17T22:30:00+05:30",
    "concept": "binary_search",
    "secondary_concepts": ["boundary_handling"],
    "test_results": {"passed": ["normal_asc", "normal_desc"], "failed": ["single_element"]},
    "failure_classes": ["single_element"],
    "static_pattern": "comparison_then_binary",
    "recurrence": false,
    "code": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low < high:\n        mid = (low + high) // 2\n        if arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid\n    return low if arr[low] == target else -1"
  }
];

const bioEvidencePool = [
  {
    "timestamp": "2026-08-17T13:00:00+05:30",
    "concept": "golgi",
    "secondary_concepts": ["rough_er"],
    "question_id": "scan_42",
    "selected_option": 1,
    "correct_option": 0,
    "distractor_pattern": "attributed_packaging_to_rer",
    "recurrence": true,
    "input_mode": "voice",
    "question_text": "Which organelle is primarily responsible for modifying, sorting, and packaging proteins for secretion?",
    "spoken_answer": "the rough ER"
  },
  {
    "timestamp": "2026-08-17T13:05:00+05:30",
    "concept": "golgi",
    "secondary_concepts": ["lysosome"],
    "question_id": "scan_43",
    "selected_option": 2,
    "correct_option": 0,
    "distractor_pattern": "attributed_synthesis_to_golgi",
    "recurrence": false,
    "input_mode": "voice",
    "question_text": "Where are hydrolytic enzymes tagged with Mannose-6-Phosphate before targeting to lysosomes?",
    "spoken_answer": "in the rough endoplasmic reticulum"
  },
  {
    "timestamp": "2026-08-17T13:10:00+05:30",
    "concept": "rough_er",
    "secondary_concepts": ["golgi"],
    "question_id": "scan_44",
    "selected_option": 1,
    "correct_option": 0,
    "distractor_pattern": "attributed_digestion_to_rer",
    "recurrence": true,
    "input_mode": "voice",
    "question_text": "Which structure synthesizes proteins via membrane-bound ribosomes on its surface?",
    "spoken_answer": "the Golgi apparatus"
  },
  {
    "timestamp": "2026-08-17T13:15:00+05:30",
    "concept": "protein_processing",
    "secondary_concepts": ["rough_er"],
    "question_id": "scan_45",
    "selected_option": 3,
    "correct_option": 0,
    "distractor_pattern": "incomplete_organelle_roles",
    "recurrence": false,
    "input_mode": "voice",
    "question_text": "Trace the flow of a secreted protein from synthesis to cell membrane release.",
    "spoken_answer": "Golgi to Rough ER to secretory vesicle"
  },
  {
    "timestamp": "2026-08-17T13:20:00+05:30",
    "concept": "golgi",
    "secondary_concepts": ["rough_er"],
    "question_id": "scan_46",
    "selected_option": 1,
    "correct_option": 0,
    "distractor_pattern": "cis_trans_polarity_error",
    "recurrence": true,
    "input_mode": "voice",
    "question_text": "Proteins enter the Golgi apparatus through which face, and exit through which face?",
    "spoken_answer": "enter trans face and exit cis face"
  },
  {
    "timestamp": "2026-08-17T13:25:00+05:30",
    "concept": "protein_processing",
    "secondary_concepts": ["golgi"],
    "question_id": "scan_47",
    "selected_option": 3,
    "correct_option": 0,
    "distractor_pattern": "cop_vesicle_misdirection",
    "recurrence": false,
    "input_mode": "voice",
    "question_text": "Vesicles coated with COP II proteins transport newly synthesized proteins from...",
    "spoken_answer": "Golgi back to Rough ER"
  }
];

function getRandomEvidence(domain) {
  const pool = domain === 'DSA' ? dsaEvidencePool : bioEvidencePool;
  return pool[Math.floor(Math.random() * pool.length)];
}

// Routing & Navigation
function showScreen(screenName) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const target = document.querySelector(`[data-screen="${screenName}"]`);
  if (target) target.classList.add('active');

  if (screenName === 'dashboard') {
    document.getElementById('nav-map').disabled = false;
    document.getElementById('nav-privacy').disabled = false;
  }
}

document.getElementById('nav-home').addEventListener('click', () => {
  if (confirm("End session and return to home?")) {
    resetSession();
    showScreen('landing');
  }
});

document.getElementById('nav-map').addEventListener('click', async () => {
  if (state.sessionId) {
    try {
      const mapData = await api.getLearningMap(state.sessionId);
      document.getElementById('knowledge-map-container').textContent = mapData.map_text;
      showScreen('map');
    } catch (err) {
      alert("Failed to load knowledge map: " + err.message);
    }
  }
});

document.getElementById('nav-privacy').addEventListener('click', async () => {
  if (state.sessionId) {
    try {
      const pData = await api.getPrivacy(state.sessionId);
      document.getElementById('privacy-capsule-container').textContent = JSON.stringify(pData, null, 2);
      showScreen('privacy');
    } catch (err) {
      alert("Failed to load privacy capsule: " + err.message);
    }
  }
});

document.querySelectorAll('.btn-back-to-dash').forEach(btn => {
  btn.onclick = () => showScreen('dashboard');
});

function resetSession() {
  state.sessionId = null;
  state.domain = null;
  state.loopStage = 0;
  state.diagnosticQuestion = null;
  state.targetConcept = null;
  state.entropyBefore = 0;
  document.getElementById('panels-container').innerHTML = '';
  document.getElementById('dashboard-footer').style.display = 'none';
  document.getElementById('nav-map').disabled = true;
  document.getElementById('nav-privacy').disabled = true;
  updateStepIndicators(0);
}

// Domain Session Start
document.querySelectorAll('.start-btn').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    const card = e.target.closest('.domain-card');
    const domain = card.dataset.domain;
    btn.textContent = "Starting Session...";
    btn.disabled = true;
    try {
      const res = await api.startSession(domain);
      state.sessionId = res.session_id;
      state.domain = res.domain;

      document.getElementById('current-domain-badge').textContent = state.domain;
      document.getElementById('current-session-id').textContent = `ID: ${state.sessionId.substring(0, 8)}`;

      showScreen('dashboard');

      // Auto-trigger Stage 1: Observe with fresh random evidence
      runStep1Observe();
    } catch (err) {
      alert("Failed to start session: " + err.message);
    } finally {
      btn.textContent = `Start ${domain} Diagnostic Session →`;
      btn.disabled = false;
    }
  });
});

// Update pipeline step indicators
function updateStepIndicators(stepNum) {
  document.querySelectorAll('.step-indicator').forEach(el => {
    const s = parseInt(el.dataset.step);
    el.classList.remove('active', 'completed');
    if (s < stepNum) {
      el.classList.add('completed');
      el.querySelector('.circle').textContent = '✓';
    } else if (s === stepNum) {
      el.classList.add('active');
      el.querySelector('.circle').textContent = s;
    } else {
      el.querySelector('.circle').textContent = s;
    }
  });
}

function scrollToBottom() {
  setTimeout(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }), 60);
}

// ---------------------------------------------------------------------------
// STAGE 1: OBSERVE EVIDENCE
// ---------------------------------------------------------------------------
async function runStep1Observe() {
  updateStepIndicators(1);
  const evidence = getRandomEvidence(state.domain);

  await api.observe(state.sessionId, evidence);

  let clone;
  if (state.domain === 'DSA') {
    const tpl = document.getElementById('tpl-evidence-dsa');
    clone = tpl.content.cloneNode(true);
    clone.querySelector('.code-text').textContent = evidence.code;

    const list = clone.querySelector('.test-results-list');
    (evidence.test_results.passed || []).forEach(t => {
      const tag = document.createElement('span');
      tag.className = 'test-badge pass';
      tag.textContent = `✓ ${t} (PASS)`;
      list.appendChild(tag);
    });
    (evidence.test_results.failed || []).forEach(t => {
      const tag = document.createElement('span');
      tag.className = 'test-badge fail';
      tag.textContent = `✗ ${t} (FAIL)`;
      list.appendChild(tag);
    });

    clone.querySelector('.pattern-badge').textContent = evidence.static_pattern;
    clone.querySelector('.recurrence-badge').textContent = evidence.recurrence ? "Yes (prior sessions detected)" : "None";
  } else {
    const tpl = document.getElementById('tpl-evidence-bio');
    clone = tpl.content.cloneNode(true);
    clone.querySelector('.ocr-question-box').textContent = evidence.question_text || "Which organelle is primarily responsible for modifying, sorting, and packaging proteins for secretion?";
    clone.querySelector('.voice-answer-box').textContent = evidence.spoken_answer || "the rough ER";
    clone.querySelector('.pattern-badge').textContent = evidence.distractor_pattern;
    clone.querySelector('.recurrence-badge').textContent = evidence.recurrence ? "Yes (prior sessions detected)" : "None";
  }

  document.getElementById('panels-container').appendChild(clone);
  scrollToBottom();

  const footer = document.getElementById('dashboard-footer');
  footer.style.display = 'flex';
  const nextBtn = document.getElementById('btn-next-step');
  nextBtn.textContent = 'Run Active Bayesian Diagnosis →';
  nextBtn.onclick = runStep2Diagnose;
}

// ---------------------------------------------------------------------------
// STAGE 2: DIAGNOSE (Posterior Distribution & Entropy)
// ---------------------------------------------------------------------------
function renderHypotheses(container, hypotheses) {
  container.innerHTML = '';
  if (!hypotheses || hypotheses.length === 0) {
    container.innerHTML = '<div class="text-sm text-gray-500">No active hypotheses</div>';
    return;
  }
  const sorted = [...hypotheses].sort((a, b) => (b.p !== undefined ? b.p : b.posterior || 0) - (a.p !== undefined ? a.p : a.posterior || 0));

  sorted.forEach(hyp => {
    const row = document.createElement('div');
    row.className = 'hypothesis-row';
    const prob = hyp.p !== undefined ? hyp.p : (hyp.posterior || 0);
    const pct = (prob * 100).toFixed(1);
    const isTop = hyp === sorted[0];

    row.innerHTML = `
      <div class="hypothesis-meta">
        <span class="hypothesis-name ${isTop ? 'highlight' : ''}">${hyp.id}</span>
        <span class="hypothesis-kind">${hyp.kind || 'misconception'}</span>
      </div>
      <div class="hypothesis-bar-container">
        <div class="hypothesis-bar-fill ${isTop ? 'top-fill' : ''}" style="width: ${pct}%"></div>
        <div class="hypothesis-val">${pct}%</div>
      </div>
    `;
    container.appendChild(row);
  });
}

async function runStep2Diagnose() {
  updateStepIndicators(2);
  const footer = document.getElementById('dashboard-footer');
  const nextBtn = document.getElementById('btn-next-step');
  nextBtn.disabled = true;
  nextBtn.textContent = 'Computing Posterior...';

  const res = await api.diagnose(state.sessionId);
  state.diagnosticQuestion = res.selected_question;
  state.targetConcept = res.target;
  state.entropyBefore = res.entropy || 0;

  // Render Hypotheses Distribution Card
  const tplHyp = document.getElementById('tpl-hypothesis');
  const cloneHyp = tplHyp.content.cloneNode(true);
  cloneHyp.querySelector('.entropy-val').textContent = (res.entropy || 0).toFixed(3);
  renderHypotheses(cloneHyp.querySelector('.hypotheses-list'), res.hypotheses);
  document.getElementById('panels-container').appendChild(cloneHyp);

  if (res.selected_question) {
    // STAGE 3: ASK DIAGNOSTIC QUESTION
    updateStepIndicators(3);
    const tplAsk = document.getElementById('tpl-diagnostic');
    const cloneAsk = tplAsk.content.cloneNode(true);
    cloneAsk.querySelector('.why-asking-text').textContent = res.why_asking || "AURA selected this question to maximize expected Information Gain across competing hypotheses.";
    cloneAsk.querySelector('.question-prompt').textContent = res.selected_question.prompt;

    const optionsList = cloneAsk.querySelector('.options-list');
    (res.selected_question.options || []).forEach((opt, idx) => {
      const btn = document.createElement('button');
      btn.className = 'option-card-btn';
      btn.innerHTML = `
        <span class="opt-key">${String.fromCharCode(65 + idx)}</span>
        <span class="opt-text">${opt}</span>
      `;
      btn.onclick = () => runStep3Answer(idx, btn, optionsList);
      optionsList.appendChild(btn);
    });

    const btnNextQ = cloneAsk.querySelector('.btn-next-question');
    if (btnNextQ) {
      btnNextQ.onclick = async () => {
        btnNextQ.disabled = true;
        btnNextQ.textContent = "Selecting alternate...";
        try {
          const nextRes = await api.nextQuestion(state.sessionId);
          if (nextRes.selected_question) {
            state.diagnosticQuestion = nextRes.selected_question;
            const card = btnNextQ.closest('.panel');
            card.querySelector('.why-asking-text').textContent = nextRes.why_asking || "AURA selected this question to maximize expected Information Gain across competing hypotheses.";
            card.querySelector('.question-prompt').textContent = nextRes.selected_question.prompt;
            const optList = card.querySelector('.options-list');
            optList.innerHTML = '';
            (nextRes.selected_question.options || []).forEach((opt, idx) => {
              const btn = document.createElement('button');
              btn.className = 'option-card-btn';
              btn.innerHTML = `
                <span class="opt-key">${String.fromCharCode(65 + idx)}</span>
                <span class="opt-text">${opt}</span>
              `;
              btn.onclick = () => runStep3Answer(idx, btn, optList);
              optList.appendChild(btn);
            });
          } else {
            alert("No alternate diagnostic questions remain for this concept.");
          }
        } catch (err) {
          alert("Failed to load alternate question: " + err.message);
        } finally {
          btnNextQ.disabled = false;
          btnNextQ.textContent = "Try Alternate Question 🔄";
        }
      };
    }

    document.getElementById('panels-container').appendChild(cloneAsk);
    footer.style.display = 'none'; // Hide until option clicked
  } else {
    footer.style.display = 'flex';
    nextBtn.textContent = 'Proceed to Gap Decision →';
    nextBtn.onclick = runStep4DecideAndTeach;
  }

  nextBtn.disabled = false;
  scrollToBottom();
}

// ---------------------------------------------------------------------------
// STAGE 3 & 4: ANSWER & POSTERIOR UPDATE
// ---------------------------------------------------------------------------
async function runStep3Answer(idx, selectedBtn, listContainer) {
  listContainer.querySelectorAll('.option-card-btn').forEach(b => b.disabled = true);
  selectedBtn.classList.add('selected');

  updateStepIndicators(4);
  const res = await api.answerDiagnostic(state.sessionId, state.diagnosticQuestion.id, idx);

  // Render Updated Posterior Card
  const tpl = document.getElementById('tpl-updated-posterior');
  const clone = tpl.content.cloneNode(true);

  const currentEntropy = res.entropy || 0;
  const wc = res.what_changed;

  if (wc) {
    clone.querySelector('.what-changed-text').textContent = `Entropy reduced by ${wc.entropy_delta} bits (${wc.entropy_before} → ${wc.entropy_after}). Leading gap hypothesis '${wc.leading_hypothesis}' probability reached ${(wc.leading_probability * 100).toFixed(1)}%.`;
  } else {
    clone.querySelector('.what-changed-text').textContent = `Posterior probability distribution updated after evaluating response.`;
  }

  clone.querySelector('.entropy-val').textContent = currentEntropy.toFixed(3);
  renderHypotheses(clone.querySelector('.hypotheses-list'), res.hypotheses);
  document.getElementById('panels-container').appendChild(clone);

  scrollToBottom();

  const footer = document.getElementById('dashboard-footer');
  footer.style.display = 'flex';
  const nextBtn = document.getElementById('btn-next-step');
  nextBtn.textContent = 'Materialize Gap & Teach →';
  nextBtn.onclick = runStep4DecideAndTeach;
}

// ---------------------------------------------------------------------------
// STAGE 5: MATERIALIZE GAP & TEACH
// ---------------------------------------------------------------------------
async function runStep4DecideAndTeach() {
  updateStepIndicators(5);
  const footer = document.getElementById('dashboard-footer');
  const nextBtn = document.getElementById('btn-next-step');
  nextBtn.disabled = true;
  nextBtn.textContent = 'Retrieving Grounded Content...';

  const target = state.targetConcept || (state.domain === 'DSA' ? 'binary_search' : 'golgi');
  const query = state.domain === 'DSA' ? 'boundary interval shrink' : 'golgi modifies sorts packages proteins';
  await api.retrieve(state.sessionId, target, query);

  const decideRes = await api.decide(state.sessionId);

  if (decideRes.decision === 'abstain') {
    const card = document.createElement('div');
    card.className = 'panel card appear border-amber';
    card.innerHTML = `
      <div class="panel-header text-amber-600">
        <span class="panel-label">ABSTENTION — INSUFFICIENT EVIDENCE</span>
      </div>
      <div class="panel-body">
        <p class="mb-2"><strong>Reason:</strong> ${decideRes.reason}</p>
        <p class="text-sm text-gray-500">AURA abstains from forcing a guess when confidence does not clear the threshold.</p>
      </div>
    `;
    document.getElementById('panels-container').appendChild(card);
  } else if (decideRes.gap) {
    const tplGap = document.getElementById('tpl-gap');
    const cloneGap = tplGap.content.cloneNode(true);
    cloneGap.querySelector('.gap-concept').textContent = decideRes.gap.concept_id;
    cloneGap.querySelector('.gap-class').textContent = decideRes.gap.misconception_class || 'None';
    cloneGap.querySelector('.gap-prob').textContent = (decideRes.gap.hypothesis_probability * 100).toFixed(1) + '%';
    cloneGap.querySelector('.gap-status-badge').textContent = decideRes.gap.status;
    cloneGap.querySelector('.gap-prereqs').textContent = (decideRes.gap.prerequisites_affected || []).join(', ') || 'None';
    document.getElementById('panels-container').appendChild(cloneGap);
  }

  const teachRes = await api.teach(state.sessionId, target);

  const tplTeach = document.getElementById('tpl-teaching');
  const cloneTeach = tplTeach.content.cloneNode(true);
  cloneTeach.querySelector('.teaching-action-badge').textContent = teachRes.action;
  cloneTeach.querySelector('.teaching-message').textContent = teachRes.message;

  const citationsContainer = cloneTeach.querySelector('.teaching-citations');
  if (teachRes.citations && teachRes.citations.length > 0) {
    citationsContainer.innerHTML = teachRes.citations.map(c => `<span class="citation-tag">${c}</span>`).join(' ');
  } else {
    citationsContainer.textContent = "dsa_corpus:bs_boundary";
  }

  document.getElementById('panels-container').appendChild(cloneTeach);

  // STAGE 6: ORIGINAL REASSESSMENT, THEN TRANSFER VERIFICATION
  updateStepIndicators(6);
  const tplTransfer = document.getElementById('tpl-transfer');
  const cloneTransfer = tplTransfer.content.cloneNode(true);
  const promptNode = cloneTransfer.querySelector('.transfer-prompt');
  promptNode.textContent =
    'First confirm that the original problem passes after the intervention. AURA will then load a curated, structurally different task on the same concept. Demo evidence is simulated.';
  const btnVerify = cloneTransfer.querySelector('.btn-submit-transfer');
  const resultNode = btnVerify.nextElementSibling;
  let transferData = null;

  const transferOutcome = document.createElement('select');
  transferOutcome.setAttribute('aria-label', 'Simulated transfer outcome');
  transferOutcome.className = 'transfer-outcome-select';
  transferOutcome.hidden = true;
  [
    ['passed', 'Simulated transfer result: passed'],
    ['failed', 'Simulated transfer result: failed'],
  ].forEach(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    transferOutcome.appendChild(option);
  });
  promptNode.insertAdjacentElement('afterend', transferOutcome);

  btnVerify.textContent = 'Confirm original pass & load transfer task';
  btnVerify.onclick = async () => {
    btnVerify.disabled = true;
    try {
      if (!transferData) {
        const originalRes = await api.markOriginalRecovered(
          state.sessionId,
          true,
          'Demo learner explicitly confirmed the original reassessment passed',
        );
        if (!originalRes.gap || originalRes.gap.status !== 'recovered_pending_transfer') {
          resultNode.classList.remove('hidden');
          resultNode.textContent = originalRes.message || 'Original reassessment is not verified; transfer remains unavailable.';
          btnVerify.textContent = 'Transfer unavailable';
          return;
        }

        const selected = await api.getTransferProblem(state.sessionId);
        if (!selected.available || !selected.transfer_problem) {
          resultNode.classList.remove('hidden');
          resultNode.textContent = selected.message || 'No eligible transfer task is available. Recovery remains unverified.';
          btnVerify.textContent = 'Transfer unavailable';
          return;
        }

        transferData = selected;
        promptNode.textContent =
          `Curated transfer task (${selected.transfer_problem.id}): ${selected.transfer_problem.prompt}`;
        transferOutcome.hidden = false;
        resultNode.classList.remove('hidden');
        resultNode.textContent = 'Original reassessment passed. Status is recovered_pending_transfer; report the simulated transfer outcome next.';
        btnVerify.textContent = 'Submit simulated transfer result';
        btnVerify.disabled = false;
        return;
      }

      btnVerify.textContent = 'Verifying Transfer Challenge...';
      const passed = transferOutcome.value === 'passed';
      const verifyRes = await api.verifyTransfer(
        state.sessionId,
        passed,
        passed ? 'Demo transfer task reported as passed' : 'Demo transfer task reported as failed',
        transferData.transfer_problem.id,
        transferData.original_problem_id,
        transferData.structurally_different,
      );

      resultNode.classList.remove('hidden');
      resultNode.innerHTML = `
        <div class="result-row"><strong>Transfer Verified:</strong> <span>${verifyRes.gap.transfer_verified}</span></div>
        <div class="result-row"><strong>Gap Lifecycle Status:</strong> <span class="badge">${verifyRes.gap.status}</span></div>
        <div class="result-row"><strong>Recovery Confidence:</strong> ${(verifyRes.gap.recovery_confidence * 100).toFixed(1)}%</div>
        <div class="result-row">${verifyRes.message}</div>
      `;

      if (verifyRes.gap.status === 'recovered' && verifyRes.gap.transfer_verified === true) {
        showRecovery(verifyRes.gap);
      } else {
        btnVerify.textContent = 'Transfer did not verify recovery';
      }
    } catch (err) {
      alert('Transfer verification failed: ' + err.message);
      btnVerify.textContent = transferData ? 'Retry transfer submission' : 'Retry original reassessment';
      btnVerify.disabled = false;
    }
  };

  document.getElementById('panels-container').appendChild(cloneTransfer);

  footer.style.display = 'none';
  nextBtn.disabled = false;
  scrollToBottom();
}

// ---------------------------------------------------------------------------
// STAGE 6 SUCCESS: RECOVERY VERIFIED
// ---------------------------------------------------------------------------
function showRecovery(gap) {
  // The success screen is gated by the authoritative API lifecycle state.
  if (!gap || gap.status !== 'recovered' || gap.transfer_verified !== true) {
    return;
  }
  const tpl = document.getElementById('tpl-recovery');
  const clone = tpl.content.cloneNode(true);

  const btnRestart = clone.querySelector('.btn-restart-session');
  if (btnRestart) {
    btnRestart.onclick = () => {
      resetSession();
      showScreen('landing');
    };
  }

  clone.querySelector('.btn-view-map').onclick = async () => {
    const mapData = await api.getLearningMap(state.sessionId);
    document.getElementById('knowledge-map-container').textContent = mapData.map_text;
    showScreen('map');
  };

  clone.querySelector('.btn-view-privacy').onclick = async () => {
    const pData = await api.getPrivacy(state.sessionId);
    document.getElementById('privacy-capsule-container').textContent = JSON.stringify(pData, null, 2);
    showScreen('privacy');
  };

  clone.querySelector('.btn-view-summary').onclick = async () => {
    const sData = await api.closeSession(state.sessionId);
    document.getElementById('summary-stats').innerHTML = `
      <pre class="code-block json-hl">${JSON.stringify(sData, null, 2)}</pre>
    `;
    showScreen('summary');
  };

  document.getElementById('panels-container').appendChild(clone);
  scrollToBottom();
}

document.getElementById('btn-back-from-privacy').onclick = () => {
  showScreen('dashboard');
};

document.getElementById('btn-home-from-summary').onclick = () => {
  resetSession();
  showScreen('landing');
};

// Initial setup
resetSession();
