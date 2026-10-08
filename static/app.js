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

function setPlacementStreak(streak) {
  setValueBeforeSuffix("placement-streak-value", streak.current_streak);
  if (streak.period_status === "completed") {
    setNote("placement-streak-note", `Final sprint streak through ${streak.as_of_date}: ${streak.current_streak} days`);
  } else if (streak.period_status === "upcoming") {
    setNote("placement-streak-note", `Sprint begins ${streak.sprint_start}`);
  } else {
    setNote("placement-streak-note", `Current sprint streak as of ${streak.as_of_date}`);
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
    setPlacementStreak(streakResult.value);
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
function renderSprintHistory(records) {
  const tableBody = document.getElementById("sprint-history-body");
  if (!tableBody) return;

  const today = getLocalDateString();
  tableBody.replaceChildren();
  records.forEach((record) => {
    const row = document.createElement("tr");
    const isToday = record.date === today;
    const isUpcoming = record.date > today;
    if (isToday) row.className = "today-row";

    const values = [
      record.date,
      `${record.score}/100`,
      `${record.deep_work_minutes} min`,
      `${record.technical_completed}/5`,
      `${record.placement_completed}/5`
    ];
    values.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value);
      row.append(cell);
    });

    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    if (isUpcoming) {
      status.className = "history-status upcoming";
      status.textContent = "Upcoming";
    } else if (isToday) {
      status.className = "history-status in-progress";
      status.textContent = "In Progress";
    } else if (Number(record.score) >= 60) {
      status.className = "history-status successful";
      status.textContent = "Successful";
    } else {
      status.className = "history-status needs-work";
      status.textContent = "Needs Work";
    }
    statusCell.append(status);
    row.append(statusCell);
    tableBody.append(row);
  });
}

async function loadSprintHistory() {
  const tableBody = document.getElementById("sprint-history-body");
  try {
    const records = await getJson("/api/sprint-history");
    if (!Array.isArray(records)) throw new Error("Invalid sprint history response");
    renderSprintHistory(records);
  } catch {
    if (tableBody) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 6;
      cell.textContent = "Sprint history couldn't be loaded.";
      row.append(cell);
      tableBody.replaceChildren(row);
    }
  }
}
async function loadSprintAnalytics() {
  const metricElements = {
    average_score: document.getElementById("analytics-average-score"),
    average_deep_work_minutes: document.getElementById("analytics-average-deep-work"),
    habit_completion_rate: document.getElementById("analytics-habit-rate"),
    successful_days: document.getElementById("analytics-successful-days"),
    best_streak: document.getElementById("analytics-best-streak")
  };
  const message = document.getElementById("analytics-message");

  try {
    const analytics = await getJson("/api/analytics");
    const values = {
      average_score: `${analytics.average_score}/100`,
      average_deep_work_minutes: `${analytics.average_deep_work_minutes} min`,
      habit_completion_rate: `${analytics.habit_completion_rate}%`,
      successful_days: String(analytics.successful_days),
      best_streak: `${analytics.best_streak} days`
    };
    Object.entries(values).forEach(([key, value]) => {
      if (metricElements[key]) metricElements[key].textContent = value;
    });
    if (message) message.hidden = true;
  } catch {
    Object.values(metricElements).forEach((element) => {
      if (element) element.textContent = "—";
    });
    if (message) {
      message.textContent = "Sprint analytics couldn't be loaded.";
      message.hidden = false;
    }
  }
}
function updateSprintDay(sprintStart, sprintEnd, today = getLocalDateString()) {
  const display = document.getElementById("sprint-day-value");
  if (!display || !sprintStart || !sprintEnd) return;

  const millisecondsPerDay = 24 * 60 * 60 * 1000;
  const startTime = Date.parse(`${sprintStart}T00:00:00Z`);
  const endTime = Date.parse(`${sprintEnd}T00:00:00Z`);
  const todayTime = Date.parse(`${today}T00:00:00Z`);
  const totalDays = Math.floor((endTime - startTime) / millisecondsPerDay) + 1;
  const elapsedDays = today < sprintStart
    ? 0
    : Math.min(totalDays, Math.floor((todayTime - startTime) / millisecondsPerDay) + 1);
  display.textContent = `Day ${elapsedDays} / ${totalDays}`;
}

function setDeepWorkState(minutes, messageText = "") {
  const display = document.getElementById("deep-work-value");
  const input = document.getElementById("deep-work-minutes");
  const button = document.getElementById("deep-work-save");
  const message = document.getElementById("deep-work-message");
  if (display && display.firstChild) {
    display.firstChild.textContent = minutes === null ? "— " : `${minutes} `;
  }
  if (input) input.disabled = minutes === null;
  if (button) button.disabled = minutes === null;
  if (message) message.textContent = messageText;
}

async function loadDailyDeepWork(today) {
  try {
    const summary = await getJson(`/api/deep-work/daily/${today}`);
    if (summary.sessions.length > 0) {
      setDeepWorkState(summary.total_minutes, "V2 session total; add another session if needed.");
      setNote("deep-work-note", `${summary.sessions.length} session${summary.sessions.length === 1 ? "" : "s"} recorded today.`);
      return summary;
    }

    try {
      const legacyEntry = await getJson(`/api/daily-entries/${today}`);
      setDeepWorkState(legacyEntry.deep_work_minutes, "Legacy daily total shown; saving adds a V2 session.");
      setNote("deep-work-note", "Showing the existing V1 daily total.");
    } catch (error) {
      if (error.status !== 404) throw error;
      setDeepWorkState(0);
      setNote("deep-work-note", "No deep-work recorded today.");
    }
    return summary;
  } catch {
    setDeepWorkState(null, "Today's deep-work total couldn't be loaded.");
    setNote("deep-work-note", "Deep-work time couldn't be loaded.");
    return null;
  }
}

async function refreshAfterDeepWorkSave(today) {
  const results = await Promise.allSettled([
    getJson(`/api/daily-score/${today}`),
    getJson("/api/placement-streak")
  ]);
  const [scoreResult, streakResult] = results;

  if (scoreResult.status === "fulfilled") {
    setValueBeforeSuffix("daily-score-value", scoreResult.value.score);
    const ring = document.getElementById("daily-score-ring");
    if (ring) ring.textContent = scoreResult.value.score;
    setNote("daily-score-note", "Your effort, added up for today");
  } else {
    setValueBeforeSuffix("daily-score-value", "—");
    setNote("daily-score-note", "Daily score couldn't be refreshed.");
  }

  if (streakResult.status === "fulfilled") {
    setPlacementStreak(streakResult.value);
    updateSprintDay(streakResult.value.sprint_start, streakResult.value.sprint_end, today);
  } else {
    setValueBeforeSuffix("placement-streak-value", "—");
    setNote("placement-streak-note", "Placement streak couldn't be refreshed.");
  }

  await Promise.all([
    loadDailyDeepWork(today),
    loadSprintAnalytics(),
    loadSprintHistory(),
    loadPlacementDashboard()
  ]);
}

async function handleDeepWorkSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("deep-work-minutes");
  const button = document.getElementById("deep-work-save");
  const message = document.getElementById("deep-work-message");
  const today = getLocalDateString();
  if (!input || !button) return;

  const enteredMinutes = input.value.trim();
  if (!/^\d+$/.test(enteredMinutes) || !Number.isSafeInteger(Number(enteredMinutes)) || Number(enteredMinutes) < 30) {
    if (message) message.textContent = "Enter a whole number of at least 30 minutes per session.";
    return;
  }

  if (message) message.textContent = "";
  button.disabled = true;
  try {
    const category = document.getElementById("deep-work-category")?.value || "Other";
    const response = await fetch("/api/deep-work/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: today, duration_minutes: Number(enteredMinutes), category })
    });
    if (response.status === 409) {
      await loadDailyDeepWork(today);
      if (message) message.textContent = "Today's deep-work session could not be saved; refresh the total and try again.";
      return;
    }
    if (!response.ok) {
      throw new Error("Couldn't save deep-work minutes. Please try again.");
    }

    input.value = "30";
    if (message) message.textContent = "Deep-work session saved.";
    setNote("deep-work-note", "Recorded a V2 deep-work session for today.");
    await refreshAfterDeepWorkSave(today);
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
  void loadSprintHistory();
  void loadSprintAnalytics();
  document.getElementById("deep-work-form")?.addEventListener("submit", handleDeepWorkSubmit);
  void loadDailyDeepWork(today);
  const results = await Promise.allSettled([
    getJson("/api/habits/today"),
    getJson(`/api/daily-score/${today}`),
    getJson("/api/placement-streak")
  ]);

  const [habitsResult, scoreResult, streakResult] = results;

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
    setPlacementStreak(streakResult.value);
    updateSprintDay(streakResult.value.sprint_start, streakResult.value.sprint_end, today);
  } else {
    setValueBeforeSuffix("placement-streak-value", "—");
    setNote("placement-streak-note", "Placement streak couldn't be loaded.");
  }

  if (habitsResult.status === "fulfilled" && Array.isArray(habitsResult.value)) {
    renderHabits(habitsResult.value);
  } else {
    const habitList = document.getElementById("habit-list");
    if (habitList) habitList.textContent = "Habit list couldn't be loaded.";
  }
}


function formatMinutes(minutes) {
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours && remainder) return `${hours}h ${remainder}m`;
  if (hours) return `${hours}h`;
  return `${remainder}m`;
}

function createTextElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = String(text);
  return element;
}

function renderDashboardList(containerId, entries, emptyMessage, renderEntry) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.replaceChildren();
  if (!entries.length) {
    container.append(createTextElement("p", "panel-description", emptyMessage));
    return;
  }
  entries.forEach((entry) => container.append(renderEntry(entry)));
}

function renderPlacementDashboard(data) {
  const goal = document.getElementById("dashboard-goal-value");
  const goalInput = document.getElementById("dashboard-goal-input");
  const targetInput = document.getElementById("dashboard-target-input");
  if (goal) goal.textContent = data.goal;
  if (goalInput && document.activeElement !== goalInput) goalInput.value = data.goal;
  if (targetInput && document.activeElement !== targetInput) {
    targetInput.value = String(data.deep_work.daily.target_minutes);
  }

  const active = document.getElementById("dashboard-active-applications");
  if (active) active.textContent = String(data.applications.active);
  const prepPercent = document.getElementById("dashboard-preparation-percent");
  if (prepPercent) prepPercent.textContent = `${data.preparation.completion_percentage}%`;
  const prepCount = document.getElementById("dashboard-preparation-count");
  if (prepCount) prepCount.textContent = `${data.preparation.completed}/${data.preparation.total_topics} topics completed`;

  const daily = data.deep_work.daily;
  const deepPercent = document.getElementById("dashboard-deep-work-percent");
  if (deepPercent) deepPercent.textContent = `${daily.progress_percentage}%`;
  const deepActual = document.getElementById("dashboard-deep-work-actual");
  if (deepActual) deepActual.textContent = `${formatMinutes(daily.actual_minutes)} of ${formatMinutes(daily.target_minutes)}`;
  const dailyText = document.getElementById("dashboard-deep-work-daily-text");
  if (dailyText) dailyText.textContent = `${formatMinutes(daily.actual_minutes)} / ${formatMinutes(daily.target_minutes)}`;
  const dailyProgress = document.getElementById("dashboard-deep-work-daily-progress");
  if (dailyProgress) dailyProgress.textContent = `${daily.progress_percentage}% progress`;
  const dailyBar = document.getElementById("dashboard-deep-work-daily-bar");
  if (dailyBar) dailyBar.style.width = `${Math.min(daily.progress_percentage, 100)}%`;

  const weekly = data.deep_work.weekly;
  const weeklyText = document.getElementById("dashboard-deep-work-weekly-text");
  if (weeklyText) weeklyText.textContent = `${formatMinutes(weekly.actual_minutes)} / ${formatMinutes(weekly.target_minutes)}`;
  const weeklyProgress = document.getElementById("dashboard-deep-work-weekly-progress");
  if (weeklyProgress) weeklyProgress.textContent = `${weekly.progress_percentage}% progress · Monday to today`;
  const weeklyBar = document.getElementById("dashboard-deep-work-weekly-bar");
  if (weeklyBar) weeklyBar.style.width = `${Math.min(weekly.progress_percentage, 100)}%`;

  const pipelineList = document.getElementById("dashboard-pipeline-list");
  if (pipelineList) {
    pipelineList.replaceChildren();
    Object.entries(data.applications.pipeline).forEach(([status, count]) => {
      const item = document.createElement("div");
      item.className = "pipeline-item";
      item.append(createTextElement("span", "", status), createTextElement("strong", "", count));
      pipelineList.append(item);
    });
  }

  const deadlineContainer = document.getElementById("dashboard-next-deadline");
  if (deadlineContainer) {
    deadlineContainer.replaceChildren();
    if (data.next_deadline) {
      deadlineContainer.append(
        createTextElement("p", "deadline-company", data.next_deadline.company),
        createTextElement("p", "deadline-role", data.next_deadline.role),
        createTextElement("span", "deadline-date", data.next_deadline.deadline)
      );
    } else {
      deadlineContainer.append(createTextElement("p", "panel-description", "No upcoming deadlines."));
    }
  }

  const prep = data.preparation;
  const progressValues = {
    "preparation-total-topics": prep.total_topics,
    "preparation-completed-topics": prep.completed,
    "preparation-in-progress-topics": prep.in_progress,
    "preparation-not-started-topics": prep.not_started,
    "preparation-total-practices": prep.total_practice_count,
    "preparation-completion-percent": `${prep.completion_percentage}%`
  };
  Object.entries(progressValues).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) element.textContent = String(value);
  });
  const completionBar = document.getElementById("preparation-completion-bar");
  if (completionBar) completionBar.style.width = `${Math.min(prep.completion_percentage, 100)}%`;
  const prepSummary = document.getElementById("dashboard-preparation-summary");
  if (prepSummary) {
    prepSummary.textContent = `${prep.completed} completed · ${prep.in_progress} in progress · ${prep.not_started} not started`;
  }
  const practiceCount = document.getElementById("dashboard-practice-count");
  if (practiceCount) practiceCount.textContent = `${prep.total_practice_count} practices`;
  const categoryList = document.getElementById("dashboard-category-progress");
  if (categoryList) {
    categoryList.replaceChildren();
    prep.categories.forEach((category) => {
      const row = document.createElement("div");
      row.className = "category-progress-row";
      row.append(createTextElement("span", "", category.category));
      const track = document.createElement("div");
      track.className = "category-progress-track";
      const bar = document.createElement("span");
      bar.style.width = `${Math.min(category.completion_percentage, 100)}%`;
      track.append(bar);
      row.append(track, createTextElement("strong", "", `${category.completion_percentage}%`));
      categoryList.append(row);
    });
  }

  renderDashboardList("dashboard-mits-list", data.today.mits, "No MITs added for today.", (mit) => {
    const row = createTextElement("div", "focus-row", mit.task);
    if (mit.completed) row.append(createTextElement("small", "", "Completed"));
    return row;
  });
  renderDashboardList("dashboard-incomplete-topics", data.today.incomplete_topics, "No incomplete preparation topics.", (topic) => {
    const row = createTextElement("div", "focus-row", topic.name);
    row.append(createTextElement("small", "", `${topic.category} · ${topic.status}`));
    return row;
  });
}

async function loadPlacementDashboard() {
  const message = document.getElementById("dashboard-load-message");
  try {
    const data = await getJson("/api/dashboard");
    renderPlacementDashboard(data);
    if (message) {
      message.hidden = true;
      message.textContent = "";
    }
    return data;
  } catch {
    if (message) {
      message.hidden = false;
      message.textContent = "Placement dashboard data couldn't be loaded. Try refreshing the page.";
    }
    return null;
  }
}

async function saveDashboardSetting(payload, messageId) {
  const message = document.getElementById(messageId);
  if (message) message.textContent = "";
  try {
    const response = await fetch("/api/dashboard/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error("Couldn't save this dashboard setting.");
    await loadPlacementDashboard();
    if (message) message.textContent = "Setting saved.";
  } catch (error) {
    if (message) message.textContent = error.message;
  }
}

function handleDashboardGoalSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("dashboard-goal-input");
  if (input && input.value.trim()) {
    void saveDashboardSetting({ goal: input.value.trim() }, "dashboard-goal-message");
  }
}

function handleDashboardTargetSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("dashboard-target-input");
  if (!input || !input.reportValidity()) return;
  void saveDashboardSetting(
    { daily_deep_work_target_minutes: Number(input.value) },
    "dashboard-target-message"
  );
}

const OPPORTUNITY_STATUSES = [
  "Interested", "Applied", "Assessment", "Interview", "HR",
  "Selected", "Rejected", "Withdrawn", "Not Eligible", "Expired"
];
let opportunities = [];
let editingOpportunityId = null;

function opportunityFormPayload() {
  const value = (id) => document.getElementById(id).value.trim();
  return {
    company: value("opportunity-company"),
    role: value("opportunity-role"),
    location: value("opportunity-location") || null,
    source: value("opportunity-source") || null,
    job_link: value("opportunity-job-link") || null,
    status: document.getElementById("opportunity-status").value,
    priority: document.getElementById("opportunity-priority").value,
    ctc: value("opportunity-ctc") || null,
    deadline: document.getElementById("opportunity-deadline").value || null,
    referral: value("opportunity-referral") || null,
    eligibility: value("opportunity-eligibility") || null,
    requirements: value("opportunity-requirements") || null,
    notes: value("opportunity-notes") || null,
    is_serious: document.getElementById("opportunity-serious").checked
  };
}

function resetOpportunityForm() {
  document.getElementById("opportunity-form").reset();
  document.getElementById("opportunity-form-title").textContent = "Add an opportunity";
  document.getElementById("opportunity-save-button").textContent = "Save opportunity";
  document.getElementById("opportunity-cancel-edit").hidden = true;
  document.getElementById("opportunity-message").textContent = "";
  editingOpportunityId = null;
}

function beginOpportunityEdit(opportunity) {
  editingOpportunityId = opportunity.id;
  document.getElementById("opportunity-form-title").textContent = "Edit opportunity";
  document.getElementById("opportunity-save-button").textContent = "Save changes";
  document.getElementById("opportunity-cancel-edit").hidden = false;
  const values = {
    "opportunity-company": opportunity.company,
    "opportunity-role": opportunity.role,
    "opportunity-location": opportunity.location || "",
    "opportunity-source": opportunity.source || "",
    "opportunity-job-link": opportunity.job_link || "",
    "opportunity-status": opportunity.status,
    "opportunity-priority": opportunity.priority,
    "opportunity-ctc": opportunity.ctc || "",
    "opportunity-deadline": opportunity.deadline || "",
    "opportunity-referral": opportunity.referral || "",
    "opportunity-eligibility": opportunity.eligibility || "",
    "opportunity-requirements": opportunity.requirements || "",
    "opportunity-notes": opportunity.notes || "",
    "opportunity-serious": Boolean(opportunity.is_serious)
  };
  Object.entries(values).forEach(([id, value]) => {
    const input = document.getElementById(id);
    if (id === "opportunity-serious") input.checked = value;
    else input.value = value;
  });
  document.getElementById("opportunity-management").scrollIntoView({ behavior: "smooth", block: "start" });
}

function appendOpportunityDetail(card, label, value) {
  if (!value) return;
  const detail = document.createElement("p");
  detail.className = "opportunity-card-detail";
  const name = document.createElement("strong");
  name.textContent = `${label}: `;
  detail.append(name, document.createTextNode(value));
  card.append(detail);
}

function opportunityStatusSelect(opportunity) {
  const select = document.createElement("select");
  select.className = "opportunity-status-select";
  select.setAttribute("aria-label", `Status for ${opportunity.company} ${opportunity.role}`);
  OPPORTUNITY_STATUSES.forEach((status) => {
    const option = document.createElement("option");
    option.value = status;
    option.textContent = status;
    option.selected = status === opportunity.status;
    select.append(option);
  });
  select.addEventListener("change", () => {
    const previousStatus = opportunity.status;
    void updateOpportunity(opportunity.id, { status: select.value }, "Opportunity status updated.")
      .catch((error) => {
        select.value = previousStatus;
        setOpportunityListMessage(error.message || "Couldn't update opportunity status.");
      });
  });
  return select;
}

function renderOpportunityCard(opportunity, container) {
  const card = document.createElement("article");
  card.className = "opportunity-card";
  const heading = document.createElement("h4");
  heading.textContent = opportunity.company;
  card.append(heading);
  const role = document.createElement("p");
  role.className = "opportunity-card-role";
  role.textContent = opportunity.role;
  card.append(role);

  const badges = document.createElement("div");
  badges.className = "opportunity-card-meta";
  const seriousBadge = document.createElement("span");
  seriousBadge.className = `opportunity-badge${opportunity.is_serious ? " serious" : ""}`;
  seriousBadge.textContent = opportunity.is_serious ? "Serious Application" : "Inbox";
  const priorityBadge = document.createElement("span");
  priorityBadge.className = `opportunity-badge${opportunity.priority === "High" ? " priority-high" : opportunity.priority === "Low" ? " priority-low" : ""}`;
  priorityBadge.textContent = `${opportunity.priority} priority`;
  badges.append(seriousBadge, priorityBadge, opportunityStatusSelect(opportunity));
  if (opportunity.location) badges.append(createTextElement("span", "opportunity-badge", opportunity.location));
  if (opportunity.deadline) badges.append(createTextElement("span", "opportunity-badge", `Deadline ${opportunity.deadline}`));
  card.append(badges);

  const sourceDetails = [
    ["Source", opportunity.source], ["CTC", opportunity.ctc],
    ["Referral", opportunity.referral], ["Eligibility", opportunity.eligibility],
    ["Requirements", opportunity.requirements], ["Notes", opportunity.notes]
  ];
  sourceDetails.forEach(([label, value]) => appendOpportunityDetail(card, label, value));

  if (opportunity.job_link) {
    try {
      const linkUrl = new URL(opportunity.job_link, window.location.origin);
      if (linkUrl.protocol === "http:" || linkUrl.protocol === "https:") {
        const link = document.createElement("a");
        link.className = "opportunity-card-link";
        link.href = linkUrl.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Open job link";
        card.append(link);
      }
    } catch { /* Ignore malformed optional links. */ }
  }

  const actions = document.createElement("div");
  actions.className = "opportunity-card-actions";
  const seriousButton = document.createElement("button");
  seriousButton.type = "button";
  seriousButton.className = "secondary-button";
  seriousButton.textContent = opportunity.is_serious ? "Move to inbox" : "Mark serious";
  seriousButton.addEventListener("click", () => {
    void updateOpportunity(
      opportunity.id,
      { is_serious: !opportunity.is_serious },
      opportunity.is_serious ? "Moved to Opportunity Inbox." : "Promoted to Serious Applications."
    ).catch((error) => setOpportunityListMessage(error.message || "Couldn't update this opportunity."));
  });

  const editButton = document.createElement("button");
  editButton.type = "button";
  editButton.className = "secondary-button";
  editButton.textContent = "Edit";
  editButton.addEventListener("click", () => beginOpportunityEdit(opportunity));

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "delete-button";
  deleteButton.textContent = "Delete";
  deleteButton.addEventListener("click", () => void deleteOpportunity(opportunity));
  actions.append(seriousButton, editButton, deleteButton);
  card.append(actions);
  container.append(card);
}

function setOpportunityListMessage(message) {
  const element = document.getElementById("opportunity-list-message");
  if (element) element.textContent = message;
}

function renderOpportunityLists() {
  const inbox = document.getElementById("opportunity-inbox-list");
  const serious = document.getElementById("opportunity-serious-list");
  const statusFilter = document.getElementById("opportunity-filter-status").value;
  const priorityFilter = document.getElementById("opportunity-filter-priority").value;
  const seriousFilter = document.getElementById("opportunity-filter-serious").value;
  const filtered = opportunities.filter((item) =>
    (!statusFilter || item.status === statusFilter)
    && (!priorityFilter || item.priority === priorityFilter)
    && (seriousFilter === "" || String(item.is_serious) === seriousFilter)
  );
  const inboxItems = filtered.filter((item) => !item.is_serious);
  const seriousItems = filtered.filter((item) => item.is_serious);
  document.getElementById("opportunity-inbox-count").textContent = String(inboxItems.length);
  document.getElementById("opportunity-serious-count").textContent = String(seriousItems.length);
  inbox.replaceChildren();
  serious.replaceChildren();
  if (inboxItems.length === 0) {
    inbox.textContent = opportunities.length === 0 ? "No opportunities added yet." : "No inbox opportunities match these filters.";
  } else {
    inboxItems.forEach((item) => renderOpportunityCard(item, inbox));
  }
  if (seriousItems.length === 0) {
    serious.textContent = opportunities.length === 0 ? "No serious applications yet." : "No serious applications match these filters.";
  } else {
    seriousItems.forEach((item) => renderOpportunityCard(item, serious));
  }
}

async function loadOpportunities() {
  try {
    opportunities = await requestApi("/api/opportunities");
    renderOpportunityLists();
  } catch (error) {
    document.getElementById("opportunity-inbox-list").textContent = "Opportunities couldn't be loaded.";
    document.getElementById("opportunity-serious-list").textContent = "Serious applications couldn't be loaded.";
    setOpportunityListMessage(error.message || "Couldn't load opportunities. Please try again.");
  }
}

async function updateOpportunity(opportunityId, changes, successMessage) {
  await requestApi(`/api/opportunities/${opportunityId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes)
  });
  await Promise.all([loadOpportunities(), loadPlacementDashboard()]);
  setOpportunityListMessage(successMessage);
}

async function deleteOpportunity(opportunity) {
  const confirmed = window.confirm(`Delete ${opportunity.company} ? ${opportunity.role}? This cannot be undone.`);
  if (!confirmed) return;
  try {
    await requestApi(`/api/opportunities/${opportunity.id}`, { method: "DELETE" });
    if (editingOpportunityId === opportunity.id) resetOpportunityForm();
    await Promise.all([loadOpportunities(), loadPlacementDashboard()]);
    setOpportunityListMessage("Opportunity deleted.");
  } catch (error) {
    setOpportunityListMessage(error.message || "Couldn't delete this opportunity.");
  }
}

async function handleOpportunitySubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const method = editingOpportunityId === null ? "POST" : "PUT";
  const path = editingOpportunityId === null
    ? "/api/opportunities"
    : `/api/opportunities/${editingOpportunityId}`;
  const message = document.getElementById("opportunity-message");
  const button = document.getElementById("opportunity-save-button");
  button.disabled = true;
  if (message) message.textContent = "";
  try {
    await requestApi(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opportunityFormPayload())
    });
    resetOpportunityForm();
    if (message) message.textContent = method === "POST" ? "Opportunity added." : "Opportunity updated.";
    setOpportunityListMessage("");
    await Promise.all([loadOpportunities(), loadPlacementDashboard()]);
  } catch (error) {
    if (message) {
      message.textContent = error.status === 422
        ? "Check the required fields and selected values, then try again."
        : error.message || "Couldn't save this opportunity.";
    }
  } finally {
    button.disabled = false;
  }
}

function opportunityFiltersChanged() {
  renderOpportunityLists();
}

let preparationCategories = [];
let preparationTopics = [];
let editingPreparationTopicId = null;

function populatePreparationCategoryControls() {
  const categoryInput = document.getElementById("preparation-category");
  const categoryFilter = document.getElementById("preparation-filter-category");
  const selectedCategory = categoryInput.value;
  const selectedFilter = categoryFilter.value;
  categoryInput.replaceChildren(createTextElement("option", "", "Select a category"));
  categoryInput.options[0].value = "";
  categoryFilter.replaceChildren(createTextElement("option", "", "All categories"));
  categoryFilter.options[0].value = "";

  preparationCategories.forEach((category) => {
    const formOption = createTextElement("option", "", category.name);
    formOption.value = String(category.id);
    categoryInput.append(formOption);
    const filterOption = createTextElement("option", "", category.name);
    filterOption.value = String(category.id);
    categoryFilter.append(filterOption);
  });
  if (preparationCategories.some((category) => String(category.id) === selectedCategory)) {
    categoryInput.value = selectedCategory;
  }
  if (preparationCategories.some((category) => String(category.id) === selectedFilter)) {
    categoryFilter.value = selectedFilter;
  }

  const statusFilter = document.getElementById("preparation-filter-status");
  if (statusFilter.options.length === 1) {
    Array.from(document.getElementById("preparation-status").options).forEach((status) => {
      const option = createTextElement("option", "", status.textContent);
      option.value = status.value;
      statusFilter.append(option);
    });
  }
  categoryInput.disabled = preparationCategories.length === 0;
  document.getElementById("preparation-save-button").disabled = preparationCategories.length === 0;
}

function resetPreparationForm() {
  document.getElementById("preparation-form").reset();
  document.getElementById("preparation-form-title").textContent = "Add a topic";
  document.getElementById("preparation-save-button").textContent = "Save topic";
  document.getElementById("preparation-cancel-edit").hidden = true;
  document.getElementById("preparation-form-message").textContent = "";
  editingPreparationTopicId = null;
}

function beginPreparationEdit(topic) {
  editingPreparationTopicId = topic.id;
  document.getElementById("preparation-form-title").textContent = "Edit topic";
  document.getElementById("preparation-save-button").textContent = "Save changes";
  document.getElementById("preparation-cancel-edit").hidden = false;
  document.getElementById("preparation-category").value = String(topic.category_id);
  document.getElementById("preparation-name").value = topic.name;
  document.getElementById("preparation-status").value = topic.status;
  document.getElementById("preparation-notes").value = topic.notes || "";
  document.getElementById("preparation-management").scrollIntoView({ behavior: "smooth", block: "start" });
}

function setPreparationListMessage(message) {
  document.getElementById("preparation-list-message").textContent = message;
}

function renderPreparationTopics() {
  const container = document.getElementById("preparation-topic-groups");
  const categoryFilter = document.getElementById("preparation-filter-category").value;
  const statusFilter = document.getElementById("preparation-filter-status").value;
  const filtered = preparationTopics.filter((topic) =>
    (!categoryFilter || String(topic.category_id) === categoryFilter)
    && (!statusFilter || topic.status === statusFilter)
  );
  container.replaceChildren();
  if (preparationCategories.length === 0) {
    const empty = document.createElement("p");
    empty.className = "panel-description";
    empty.textContent = "No preparation categories are available.";
    container.append(empty);
    return;
  }
  if (filtered.length === 0) {
    const empty = document.createElement("p");
    empty.className = "panel-description";
    empty.textContent = preparationTopics.length === 0
      ? "No topics yet. Add a topic above to start your preparation plan."
      : "No topics match these filters.";
    container.append(empty);
    return;
  }

  preparationCategories.forEach((category) => {
    const items = filtered.filter((topic) => topic.category_id === category.id);
    if (items.length === 0) return;
    const group = document.createElement("section");
    group.className = "preparation-topic-group";
    const heading = document.createElement("div");
    heading.className = "preparation-topic-group-heading";
    heading.append(
      createTextElement("h3", "", category.name),
      createTextElement("span", "count-pill", `${items.length} ${items.length === 1 ? "topic" : "topics"}`)
    );
    const list = document.createElement("div");
    list.className = "preparation-topic-list";
    items.forEach((topic) => {
      const card = document.createElement("article");
      card.className = "preparation-topic-card";
      card.append(createTextElement("h4", "", topic.name));
      const meta = document.createElement("div");
      meta.className = "preparation-topic-meta";
      const statusClass = topic.status === "Completed"
        ? "completed"
        : topic.status === "In Progress" ? "in-progress" : "";
      meta.append(
        createTextElement("span", `preparation-topic-status ${statusClass}`, topic.status),
        createTextElement("span", "", `${topic.practice_count} ${topic.practice_count === 1 ? "practice" : "practices"}`)
      );
      card.append(meta);
      if (topic.notes) card.append(createTextElement("p", "preparation-topic-notes", topic.notes));

      const actions = document.createElement("div");
      actions.className = "opportunity-card-actions";
      const practice = document.createElement("button");
      practice.type = "button";
      practice.textContent = "Practice";
      practice.addEventListener("click", () => void recordPreparationPractice(topic.id));
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "secondary-button";
      edit.textContent = "Edit";
      edit.addEventListener("click", () => beginPreparationEdit(topic));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "delete-button";
      remove.textContent = "Delete";
      remove.addEventListener("click", () => void deletePreparationTopic(topic));
      actions.append(practice, edit, remove);
      card.append(actions);
      list.append(card);
    });
    group.append(heading, list);
    container.append(group);
  });
}

async function loadPreparation() {
  try {
    const [categories, topics] = await Promise.all([
      requestApi("/api/preparation/categories"),
      requestApi("/api/preparation/topics")
    ]);
    preparationCategories = categories;
    preparationTopics = topics;
    populatePreparationCategoryControls();
    renderPreparationTopics();
  } catch (error) {
    document.getElementById("preparation-topic-groups").textContent =
      "Preparation topics couldn't be loaded. Please try again.";
    setPreparationListMessage(error.message || "Preparation data couldn't be loaded.");
  }
}

async function refreshPreparationViews(message) {
  await Promise.all([loadPreparation(), loadPlacementDashboard()]);
  setPreparationListMessage(message);
}

async function handlePreparationSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const method = editingPreparationTopicId === null ? "POST" : "PUT";
  const path = editingPreparationTopicId === null
    ? "/api/preparation/topics"
    : `/api/preparation/topics/${editingPreparationTopicId}`;
  const payload = {
    category_id: Number(document.getElementById("preparation-category").value),
    name: document.getElementById("preparation-name").value.trim(),
    status: document.getElementById("preparation-status").value,
    notes: document.getElementById("preparation-notes").value
  };
  const button = document.getElementById("preparation-save-button");
  const message = document.getElementById("preparation-form-message");
  button.disabled = true;
  message.textContent = "";
  try {
    await requestApi(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    resetPreparationForm();
    message.textContent = method === "POST" ? "Topic added." : "Topic updated.";
    await Promise.all([loadPreparation(), loadPlacementDashboard()]);
  } catch (error) {
    message.textContent = error.status === 422
      ? "Check the category, topic name, and status, then try again."
      : error.message || "Couldn't save this topic.";
  } finally {
    button.disabled = preparationCategories.length === 0;
  }
}

async function recordPreparationPractice(topicId) {
  try {
    await requestApi(`/api/preparation/topics/${topicId}/practice`, { method: "POST" });
    await refreshPreparationViews("Practice recorded. Count updated.");
  } catch (error) {
    setPreparationListMessage(error.message || "Couldn't record practice.");
  }
}

async function deletePreparationTopic(topic) {
  if (!window.confirm(`Delete ${topic.name}? This cannot be undone.`)) return;
  try {
    await requestApi(`/api/preparation/topics/${topic.id}`, { method: "DELETE" });
    if (editingPreparationTopicId === topic.id) resetPreparationForm();
    await refreshPreparationViews("Topic deleted.");
  } catch (error) {
    setPreparationListMessage(error.message || "Couldn't delete this topic.");
  }
}

function preparationFiltersChanged() {
  renderPreparationTopics();
}

let editingPerformanceEntryId = null;
let performanceOptionsLoaded = false;

async function requestApi(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch { /* Keep the readable status fallback. */ }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

function setPerformanceMessage(message) {
  const element = document.getElementById("performance-message");
  if (element) element.textContent = message;
}

function performanceFormPayload() {
  const opportunityId = document.getElementById("performance-opportunity").value;
  const topicId = document.getElementById("performance-topic").value;
  const payload = {
    date: document.getElementById("performance-date").value,
    type: document.getElementById("performance-type").value,
    performance: document.getElementById("performance-level").value,
    opportunity_id: opportunityId ? Number(opportunityId) : null,
    preparation_topic_id: topicId ? Number(topicId) : null,
    questions: document.getElementById("performance-questions").value,
    couldnt_answer: document.getElementById("performance-couldnt-answer").value,
    what_learned: document.getElementById("performance-what-learned").value,
    action_items: document.getElementById("performance-action-items").value,
    notes: document.getElementById("performance-notes").value
  };
  if (!opportunityId) {
    payload.company = document.getElementById("performance-company").value.trim() || null;
    payload.role = document.getElementById("performance-role").value.trim() || null;
  }
  return payload;
}

function resetPerformanceForm() {
  const form = document.getElementById("performance-entry-form");
  form.reset();
  document.getElementById("performance-date").value = getLocalDateString();
  document.getElementById("performance-form-title").textContent = "Record an experience";
  document.getElementById("performance-save-button").textContent = "Save Entry";
  document.getElementById("performance-cancel-edit").hidden = true;
  editingPerformanceEntryId = null;
}

async function handlePerformanceSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const method = editingPerformanceEntryId === null ? "POST" : "PUT";
  const path = editingPerformanceEntryId === null
    ? "/api/performance"
    : `/api/performance/${editingPerformanceEntryId}`;
  try {
    await requestApi(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(performanceFormPayload())
    });
    resetPerformanceForm();
    setPerformanceMessage(method === "POST" ? "Journal entry saved." : "Journal entry updated.");
    await Promise.all([loadPerformanceEntries(), loadPerformanceSummary()]);
  } catch (error) {
    setPerformanceMessage(error.message || "Couldn't save this journal entry.");
  }
}

function renderPerformanceEntries(entries) {
  const list = document.getElementById("performance-entry-list");
  if (!list) return;
  list.replaceChildren();
  if (entries.length === 0) {
    list.textContent = "No performance entries match these filters.";
    return;
  }
  entries.forEach((entry) => {
    const card = document.createElement("article");
    card.className = "performance-entry-card";
    const title = document.createElement("h4");
    title.textContent = `${entry.type} \u2014 ${entry.performance}`;
    const badge = document.createElement("span");
    badge.className = "performance-entry-badge";
    badge.textContent = entry.date;
    title.append(badge);
    card.append(title);
    const identity = [entry.company, entry.role].filter(Boolean).join(" \u00b7 ");
    const meta = document.createElement("p");
    meta.className = "performance-entry-meta";
    meta.textContent = identity || "Personal practice";
    card.append(meta);
    const fields = [
      ["Questions", entry.questions],
      ["Couldn't answer", entry.couldnt_answer],
      ["What I learned", entry.what_learned],
      ["Action items", entry.action_items],
      ["Notes", entry.notes]
    ];
    fields.forEach(([label, value]) => {
      if (!value) return;
      const field = document.createElement("p");
      field.className = "performance-entry-field";
      const strong = document.createElement("strong");
      strong.textContent = `${label}: `;
      field.append(strong, document.createTextNode(value));
      card.append(field);
    });
    const links = [];
    if (entry.preparation_topic_name) {
      links.push(entry.preparation_category
        ? `${entry.preparation_category} \u2192 ${entry.preparation_topic_name}`
        : entry.preparation_topic_name);
    }
    if (entry.opportunity_id) links.push("Linked opportunity");
    if (links.length) {
      const linkNote = document.createElement("p");
      linkNote.className = "performance-entry-links";
      linkNote.textContent = links.join(" \u00b7 ");
      card.append(linkNote);
    }
    const actions = document.createElement("div");
    actions.className = "performance-entry-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "secondary-button";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => beginPerformanceEdit(entry));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete-button";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => void deletePerformanceEntry(entry.id));
    actions.append(edit, remove);
    card.append(actions);
    list.append(card);
  });
}

async function loadPerformanceEntries() {
  const list = document.getElementById("performance-entry-list");
  if (!list) return;
  const params = new URLSearchParams();
  const filters = [
    ["type", "performance-filter-type"],
    ["performance", "performance-filter-level"],
    ["company", "performance-filter-company"],
    ["date", "performance-filter-date"]
  ];
  filters.forEach(([key, id]) => {
    const value = document.getElementById(id)?.value.trim();
    if (value) params.set(key, value);
  });
  try {
    const entries = await getJson(`/api/performance${params.size ? `?${params}` : ""}`);
    renderPerformanceEntries(entries);
  } catch {
    list.textContent = "Performance entries couldn't be loaded. Try refreshing the page.";
  }
}

async function loadPerformanceSummary() {
  try {
    const summary = await getJson("/api/performance/summary");
    document.getElementById("performance-total").textContent = `${summary.total} ${summary.total === 1 ? "entry" : "entries"}`;
    document.getElementById("performance-summary-levels").textContent =
      `Good ${summary.by_performance.Good} \u00b7 Mixed ${summary.by_performance.Mixed} \u00b7 Poor ${summary.by_performance.Poor}`;
  } catch {
    document.getElementById("performance-summary-levels").textContent = "Summary couldn't be loaded.";
  }
}

async function loadPerformanceOptions() {
  if (performanceOptionsLoaded) return;
  const [opportunities, topics] = await Promise.all([
    getJson("/api/opportunities"),
    getJson("/api/preparation/topics")
  ]);
  const opportunitySelect = document.getElementById("performance-opportunity");
  opportunities.forEach((opportunity) => {
    const option = document.createElement("option");
    option.value = opportunity.id;
    option.textContent = `${opportunity.company} \u2014 ${opportunity.role}`;
    opportunitySelect.append(option);
  });
  const topicSelect = document.getElementById("performance-topic");
  topics.forEach((topic) => {
    const option = document.createElement("option");
    option.value = topic.id;
    option.textContent = `${topic.category} \u2192 ${topic.name}`;
    topicSelect.append(option);
  });
  performanceOptionsLoaded = true;
}

function beginPerformanceEdit(entry) {
  editingPerformanceEntryId = entry.id;
  document.getElementById("performance-form-title").textContent = "Edit journal entry";
  document.getElementById("performance-save-button").textContent = "Save Changes";
  document.getElementById("performance-cancel-edit").hidden = false;
  const values = {
    "performance-company": entry.company || "",
    "performance-role": entry.role || "",
    "performance-date": entry.date,
    "performance-type": entry.type,
    "performance-level": entry.performance,
    "performance-opportunity": entry.opportunity_id || "",
    "performance-topic": entry.preparation_topic_id || "",
    "performance-questions": entry.questions,
    "performance-couldnt-answer": entry.couldnt_answer,
    "performance-what-learned": entry.what_learned,
    "performance-action-items": entry.action_items,
    "performance-notes": entry.notes
  };
  Object.entries(values).forEach(([id, value]) => { document.getElementById(id).value = value; });
  document.getElementById("performance-journal-title").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function deletePerformanceEntry(entryId) {
  try {
    await requestApi(`/api/performance/${entryId}`, { method: "DELETE" });
    setPerformanceMessage("Journal entry deleted.");
    await Promise.all([loadPerformanceEntries(), loadPerformanceSummary()]);
  } catch (error) {
    setPerformanceMessage(error.message || "Couldn't delete this journal entry.");
  }
}

function performanceFiltersChanged() {
  void loadPerformanceEntries();
}

document.getElementById("preparation-form")?.addEventListener("submit", handlePreparationSubmit);
document.getElementById("preparation-cancel-edit")?.addEventListener("click", resetPreparationForm);
["preparation-filter-category", "preparation-filter-status"].forEach((id) => {
  document.getElementById(id)?.addEventListener("change", preparationFiltersChanged);
});
void loadPreparation();
document.getElementById("opportunity-form")?.addEventListener("submit", handleOpportunitySubmit);
document.getElementById("opportunity-cancel-edit")?.addEventListener("click", resetOpportunityForm);
["opportunity-filter-status", "opportunity-filter-priority", "opportunity-filter-serious"].forEach((id) => {
  document.getElementById(id)?.addEventListener("change", opportunityFiltersChanged);
});
void loadOpportunities();
document.getElementById("mit-form")?.addEventListener("submit", handleMitSubmit);
document.getElementById("reflection-form")?.addEventListener("submit", handleReflectionSubmit);
document.getElementById("dashboard-goal-form")?.addEventListener("submit", handleDashboardGoalSubmit);
document.getElementById("dashboard-target-form")?.addEventListener("submit", handleDashboardTargetSubmit);
document.getElementById("performance-entry-form")?.addEventListener("submit", handlePerformanceSubmit);
document.getElementById("performance-cancel-edit")?.addEventListener("click", resetPerformanceForm);
["performance-filter-type", "performance-filter-level", "performance-filter-company", "performance-filter-date"].forEach((id) => {
  const input = document.getElementById(id);
  input?.addEventListener(input.tagName === "SELECT" ? "change" : "input", performanceFiltersChanged);
});
if (document.getElementById("performance-entry-form")) {
  document.getElementById("performance-date").value = getLocalDateString();
  void Promise.all([loadPerformanceOptions(), loadPerformanceEntries(), loadPerformanceSummary()]).catch(() => {
    const list = document.getElementById("performance-entry-list");
    if (list) list.textContent = "Journal options couldn't be loaded. Please refresh to try again.";
  });
}
void loadPlacementDashboard();

loadDashboard().catch(() => {
  const habitList = document.getElementById("habit-list");
  if (habitList) habitList.textContent = "The dashboard couldn't be loaded. Please refresh to try again.";
});
