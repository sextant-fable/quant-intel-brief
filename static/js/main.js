window.QuantIntelBrief = window.QuantIntelBrief || {};

const llmSettingsForm = document.querySelector("[data-llm-settings]");

if (llmSettingsForm) {
  const providerSelect = llmSettingsForm.querySelector("[data-provider-select]");
  const baseUrlInput = llmSettingsForm.querySelector("[data-base-url-input]");
  const modelInput = llmSettingsForm.querySelector("[data-model-input]");

  providerSelect.addEventListener("change", () => {
    const selected = providerSelect.options[providerSelect.selectedIndex];
    const baseUrl = selected.dataset.baseUrl || "";
    const model = selected.dataset.model || "";

    if (providerSelect.value !== "custom") {
      baseUrlInput.value = baseUrl;
      modelInput.value = model;
    }
  });
}
