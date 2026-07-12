window.QuantIntelBrief = window.QuantIntelBrief || {};

const llmSettingsForm = document.querySelector("[data-llm-settings]");

if (llmSettingsForm) {
  const providerSelect = llmSettingsForm.querySelector("[data-provider-select]");
  const baseUrlInput = llmSettingsForm.querySelector("[data-base-url-input]");
  const modelInput = llmSettingsForm.querySelector("[data-model-input]");

  providerSelect.addEventListener("change", () => {
    const selected = providerSelect.options[providerSelect.selectedIndex];

    if (providerSelect.value !== "custom") {
      baseUrlInput.value = selected.dataset.baseUrl || "";
      modelInput.value = selected.dataset.model || "";
    }
  });
}

const countdown = document.querySelector("[data-market-countdown]");

if (countdown) {
  const marketOpen = new Date(countdown.dataset.marketOpen);

  const renderCountdown = () => {
    const remaining = Math.max(0, marketOpen.getTime() - Date.now());
    const totalSeconds = Math.floor(remaining / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    countdown.textContent = [hours, minutes, seconds]
      .map((value) => String(value).padStart(2, "0"))
      .join(":");
  };

  renderCountdown();
  window.setInterval(renderCountdown, 1000);
}

document.querySelectorAll("[data-local-datetime]").forEach((element) => {
  const rawValue = element.dataset.localDatetime;
  if (!rawValue) return;
  const value = new Date(rawValue);
  if (Number.isNaN(value.getTime())) return;
  element.textContent = value.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
});

document.querySelectorAll("[data-refresh-brief]").forEach((form) => {
  form.addEventListener("submit", () => {
    const button = form.querySelector("button[type='submit']");
    if (!button) return;
    button.disabled = true;
    button.querySelector("span").textContent = "Updating...";
  });
});
