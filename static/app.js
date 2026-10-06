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

function renderMits(mits) {
  const mitList = document.getElementById("mit-list");
  if (!mitList) return;

  mitList.replaceChildren();
  if (mits.length === 0) {
    mitList.textContent = "No MITs added yet.";
    return;
  }

  mits.forEach((mit, index) => {
    const row = document.createElement("div");
    row.className = "habit-row";

    const number = document.createElement("span");
    number.className = "count-pill";
    number.textContent = String(index + 1);

    const task = document.createElement("span");
    task.className = "habit-name";
    task.textContent = mit.task;

    row.append(number, task);
    if (Object.hasOwn(mit, "completed")) {
      const status = document.createElement("span");
      status.className = `habit-category ${mit.completed ? "technical" : "placement"}`;
      status.textContent = mit.completed ? "Completed" : "Pending";
      row.append(status);
    }
    mitList.append(row);
  });
}

async function loadMits(today) {
  const mitList = document.getElementById("mit-list");
  try {
    const mits = await getJson(`/api/mits/${today}`);
    renderMits(mits);
    return true;
  } catch {
    if (mitList) mitList.textContent = "Today's MITs couldn't be loaded.";
    return false;
  }
}

async function handleMitSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("mit-input");
  const button = document.getElementById("mit-add-button");
  const today = getLocalDateString();
  const message = document.getElementById("mit-message");
  if (!input || !button) return;

  if (message) message.textContent = "";
  button.disabled = true;
  try {
    const response = await fetch("/api/mits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: today, task: input.value })
    });

    if (!response.ok) {
      const messages = {
        400: "Maximum of 3 MITs reached for today.",
        409: "This MIT already exists for today.",
        422: "Task cannot be empty."
      };
      throw new Error(messages[response.status] || "Couldn't add MIT. Please try again.");
    }

    input.value = "";
    if (!(await loadMits(today)) && message) {
      message.textContent = "MIT added, but today's list couldn't be refreshed.";
    }
  } catch (error) {
    if (message) message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
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

function setReflectionFields(reflection) {
  document.getElementById("reflection-went-well").value = reflection.went_well;
  document.getElementById("reflection-challenges").value = reflection.challenges;
  document.getElementById("reflection-improvement").value = reflection.improvement;
}

async function loadReflection(today) {
  const message = document.getElementById("reflection-message");
  try {
    const reflection = await getJson(`/api/reflections/${today}`);
    setReflectionFields(reflection);
  } catch (error) {
    if (error.status !== 404 && message) {
      message.textContent = "Today's reflection couldn't be loaded.";
    }
  }
}

async function handleReflectionSubmit(event) {
  event.preventDefault();
  const message = document.getElementById("reflection-message");
  const button = document.getElementById("reflection-save");
  const today = getLocalDateString();
  if (!button) return;

  if (message) message.textContent = "";
  button.disabled = true;
  try {
    const response = await fetch("/api/reflections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        date: today,
        went_well: document.getElementById("reflection-went-well").value,
        challenges: document.getElementById("reflection-challenges").value,
        improvement: document.getElementById("reflection-improvement").value
      })
    });

    if (response.status === 409) {
      throw new Error("Today's reflection has already been saved.");
    }
    if (!response.ok) {
      throw new Error("Couldn't save today's reflection. Please try again.");
    }
    if (message) message.textContent = "Reflection saved.";
  } catch (error) {
    if (message) message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}
async function loadDashboard() {
  const today = getLocalDateString();
  void loadMits(today);
  void loadReflection(today);
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

document.getElementById("mit-form")?.addEventListener("submit", handleMitSubmit);
document.getElementById("reflection-form")?.addEventListener("submit", handleReflectionSubmit);

loadDashboard().catch(() => {
  const habitList = document.getElementById("habit-list");
  if (habitList) habitList.textContent = "The dashboard couldn't be loaded. Please refresh to try again.";
});
