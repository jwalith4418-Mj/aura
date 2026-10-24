const API_BASE = '/api';

async function fetchApi(endpoint, options = {}) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error: ${res.status} ${text}`);
  }
  return res.json();
}

export async function startSession(domain) {
  return fetchApi('/session/start', {
    method: 'POST',
    body: JSON.stringify({ domain }),
  });
}

export async function getState(sid) {
  return fetchApi(`/session/${sid}/state`);
}

export async function observe(sid, evidence) {
  return fetchApi(`/session/${sid}/observe`, {
    method: 'POST',
    body: JSON.stringify({ evidence }),
  });
}

export async function diagnose(sid) {
  return fetchApi(`/session/${sid}/diagnose`);
}

export async function nextQuestion(sid) {
  return fetchApi(`/session/${sid}/next-question`, {
    method: 'POST'
  });
}

export async function answerDiagnostic(sid, questionId, optionIndex) {
  return fetchApi(`/session/${sid}/answer`, {
    method: 'POST',
    body: JSON.stringify({ question_id: questionId, option_index: optionIndex }),
  });
}

export async function decide(sid) {
  return fetchApi(`/session/${sid}/decide`, {
    method: 'POST'
  });
}

export async function retrieve(sid, target, query) {
  return fetchApi(`/session/${sid}/retrieve?target=${encodeURIComponent(target)}&query=${encodeURIComponent(query)}`);
}

export async function teach(sid, target) {
  return fetchApi(`/session/${sid}/teach`, {
    method: 'POST',
    body: JSON.stringify({ target }),
  });
}

export async function markOriginalRecovered(sid, passed, note, originalProblemId) {
  return fetchApi(`/session/${sid}/mark-recovered`, {
    method: 'POST',
    body: JSON.stringify({
      passed,
      note,
      original_problem_id: originalProblemId || undefined,
    }),
  });
}

export async function getTransferProblem(sid) {
  return fetchApi(`/session/${sid}/transfer-problem`);
}

export async function verifyTransfer(
  sid,
  passed,
  note,
  transferProblemId,
  originalProblemId,
  structurallyDifferent,
) {
  return fetchApi(`/session/${sid}/verify-transfer`, {
    method: 'POST',
    body: JSON.stringify({
      passed,
      note,
      transfer_problem_id: transferProblemId,
      original_problem_id: originalProblemId,
      structurally_different: structurallyDifferent === true,
    }),
  });
}

export async function getLearningMap(sid) {
  return fetchApi(`/session/${sid}/map`);
}

export async function getPrivacy(sid) {
  return fetchApi(`/session/${sid}/privacy`);
}

export async function closeSession(sid) {
  return fetchApi(`/session/${sid}/close`, {
    method: 'POST'
  });
}

export async function getDomains() {
  return fetchApi('/domains');
}

export async function getItems(sid) {
  return fetchApi(`/session/${sid}/items`);
}

export async function getGap(sid) {
  return fetchApi(`/session/${sid}/gap`);
}
