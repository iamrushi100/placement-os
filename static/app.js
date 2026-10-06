"use strict";

function getLocalDateString() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    const error = new Error(`Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function setValueBeforeSuffix(elementId, value) {
  const element = document.getElementById(elementId);
  if (element && element.firstChild) {
    element.firstChild.textContent = `${value} `;
  }
}

function setNote(elementId, message) {
  const element = document.getElementById(elementId);
  if (element) {
    element.textContent = message;
  }
}

function showDashboardMessage(message) {
  const habitList = document.getElementById("habit-list");
  if (!habitList) return;

  let status = document.getElementById("dashboard-message");
  if (!status) {
    status = document.createElement("p");
    status.id = "dashboard-message";
    status.className = "panel-description";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    habitList.after(status);
  }
  status.textContent = message;
  status.hidden = message.length === 0;
}

function appendHabitRow(container, habit) {
  const row = document.createElement("label");
  row.className = "habit-row";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = habit.completed === true;
  checkbox.disabled = false;
  checkbox.dataset.completed = String(checkbox.checked);
  checkbox.setAttribute(
    "aria-label",
    `${habit.name}: ${checkbox.checked ? "completed today" : "not completed today"}`
  );
  checkbox.addEventListener("change", () => handleHabitChange(checkbox, habit));

  const customCheck = document.createElement("span");
  customCheck.className = "custom-check";
  customCheck.setAttribute("aria-hidden", "true");

  const name = document.createElement("span");
  name.className = "habit-name";
  name.textContent = habit.name;

  const category = document.createElement("span");
  category.className = `habit-category ${habit.category === "Technical" ? "technical" : habit.category === "Placement" ? "placement" : ""}`;
  category.textContent = habit.category;

  row.append(checkbox, customCheck, name, category);
  container.append(row);
}

function renderHabits(habits) {
  const habitList = document.getElementById("habit-list");
  const count = document.getElementById("habit-count");
  if (count) count.textContent = `${habits.length} habits`;
  if (!habitList) return;

  habitList.replaceChildren();
  habits.forEach((habit) => appendHabitRow(habitList, habit));
}

async function refreshAfterCompletion(today) {
  const results = await Promise.allSettled([
    getJson("/api/habits/today"),
    getJson(`/api/daily-score/${today}`),
    getJson("/api/placement-streak")
  ]);
  const [habitsResult, scoreResult, streakResult] = results;
  const errors = [];

  if (habitsResult.status === "fulfilled" && Array.isArray(habitsResult.value)) {
    renderHabits(habitsResult.value);
  } else {
    errors.push("habit status");
  }

  if (scoreResult.status === "fulfilled") {
    setValueBeforeSuffix("daily-score-value", scoreResult.value.score);
    const ring = document.getElementById("daily-score-ring");
    if (ring) ring.textContent = scoreResult.value.score;
    setNote("daily-score-note", "Your effort, added up for today");
  } else {
    errors.push("daily score");
    setValueBeforeSuffix("daily-score-value", "—");
    setNote("daily-score-note", "Daily score couldn't be loaded.");
  }

  if (streakResult.status === "fulfilled") {
    setValueBeforeSuffix("placement-streak-value", streakResult.value.current_streak);
    setNote("placement-streak-note", "Keep showing up, one day at a time");
  } else {
    errors.push("placement streak");
    setValueBeforeSuffix("placement-streak-value", "—");
    setNote("placement-streak-note", "Placement streak couldn't be loaded.");
  }

  return errors;
}

async function handleHabitChange(checkbox, habit) {
  if (checkbox.dataset.completed === "true") {
    checkbox.checked = true;
    return;
  }
  if (!checkbox.checked) return;

  checkbox.disabled = true;
  let completionAccepted = false;
  const today = getLocalDateString();

  try {
    const response = await fetch(`/api/habits/${encodeURIComponent(habit.id)}/complete`, {
      method: "POST"
    });

    if (response.status !== 409 && !response.ok) {
      throw new Error(`Request failed (${response.status})`);
    }

    completionAccepted = true;
    checkbox.checked = true;
    checkbox.dataset.completed = "true";
    const refreshErrors = await refreshAfterCompletion(today);
    if (refreshErrors.length > 0) {
      showDashboardMessage(`Habit is complete, but ${refreshErrors.join(", ")} couldn't be refreshed.`);
    } else {
      showDashboardMessage("");
    }
  } catch (error) {
    if (completionAccepted) {
      checkbox.checked = true;
      checkbox.dataset.completed = "true";
      showDashboardMessage(`Habit is complete, but the dashboard couldn't refresh. ${error.message}`);
    } else {
      checkbox.checked = false;
      checkbox.dataset.completed = "false";
      showDashboardMessage(`Couldn't complete ${habit.name}. Please try again.`);
    }
  } finally {
    checkbox.disabled = false;
  }
}

async function loadDashboard() {
  const today = getLocalDateString();
  const results = await Promise.allSettled([
    getJson("/api/habits/today"),
    getJson(`/api/daily-score/${today}`),
    getJson("/api/placement-streak"),
    getJson(`/api/daily-entries/${today}`)
  ]);

  const [habitsResult, scoreResult, streakResult, entryResult] = results;

  if (scoreResult.status === "fulfilled") {
    const score = scoreResult.value.score;
    setValueBeforeSuffix("daily-score-value", score);
    const ring = document.getElementById("daily-score-ring");
    if (ring) ring.textContent = score;
  } else {
    setValueBeforeSuffix("daily-score-value", "—");
    const ring = document.getElementById("daily-score-ring");
    if (ring) ring.textContent = "—";
    setNote("daily-score-note", "Daily score couldn't be loaded.");
  }

  if (streakResult.status === "fulfilled") {
    setValueBeforeSuffix("placement-streak-value", streakResult.value.current_streak);
  } else {
    setValueBeforeSuffix("placement-streak-value", "—");
    setNote("placement-streak-note", "Placement streak couldn't be loaded.");
  }

  const deepWorkValue = document.getElementById("deep-work-value");
  if (entryResult.status === "fulfilled") {
    if (deepWorkValue && deepWorkValue.firstChild) {
      deepWorkValue.firstChild.textContent = `${entryResult.value.deep_work_minutes} `;
    }
    setNote("deep-work-note", "Recorded deep-work time for today.");
  } else if (entryResult.reason.status === 404) {
    if (deepWorkValue && deepWorkValue.firstChild) {
      deepWorkValue.firstChild.textContent = "0 ";
    }
    setNote("deep-work-note", "No daily entry for today.");
  } else {
    if (deepWorkValue && deepWorkValue.firstChild) {
      deepWorkValue.firstChild.textContent = "— ";
    }
    setNote("deep-work-note", "Deep-work time couldn't be loaded.");
  }

  if (habitsResult.status === "fulfilled" && Array.isArray(habitsResult.value)) {
    renderHabits(habitsResult.value);
  } else {
    const habitList = document.getElementById("habit-list");
    if (habitList) habitList.textContent = "Habit list couldn't be loaded.";
  }
}

loadDashboard().catch(() => {
  const habitList = document.getElementById("habit-list");
  if (habitList) habitList.textContent = "The dashboard couldn't be loaded. Please refresh to try again.";
});
