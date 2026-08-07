export default function({ data: config, parentElement, setTriggerValue }) {
  const app = parentElement.querySelector("#app");
  let eventSequence = 0;

  const send = (action, payload = {}) => {
    eventSequence += 1;
    setTriggerValue("event", {
      action,
      payload,
      nonce: `${Date.now()}-${eventSequence}`,
    });
  };

  const option = (value, label, selected = false) => {
    const item = document.createElement("option");
    item.value = value;
    item.textContent = label;
    item.selected = selected;
    return item;
  };

  const makeSelect = (labelText, values, unit, selectedValue, emptyLabel) => {
    const field = document.createElement("div");
    field.className = "field";
    const label = document.createElement("label");
    const select = document.createElement("select");
    const id = `field-${crypto.randomUUID()}`;
    label.htmlFor = id;
    label.textContent = labelText;
    select.id = id;
    select.setAttribute("aria-label", labelText);
    select.appendChild(option("", emptyLabel, selectedValue === null || selectedValue === undefined));
    values.forEach((value) => select.appendChild(option(
      String(value),
      `${value} ${unit}`,
      Number(selectedValue) === Number(value),
    )));
    field.append(label, select);
    return { field, select };
  };

  const showError = (message) => {
    const error = app.querySelector(".error");
    if (!error) return;
    error.textContent = message;
    error.style.display = "block";
  };

  const renderBreast = () => {
    const help = document.createElement("p");
    help.className = "help";
    help.textContent = config.help;
    const picker = makeSelect(
      config.field_label,
      config.values,
      "minutes",
      config.current,
      "Select minutes",
    );
    picker.select.addEventListener("change", () => {
      if (!picker.select.value) return;
      picker.select.disabled = true;
      send("save", { value: Number(picker.select.value) });
    });
    const actions = document.createElement("div");
    actions.className = "actions";
    actions.innerHTML = '<button type="button" data-action="clear">Clear all</button><button type="button" data-action="cancel">Cancel</button>';
    actions.querySelector('[data-action="clear"]').addEventListener("click", () => send("clear"));
    actions.querySelector('[data-action="cancel"]').addEventListener("click", () => send("cancel"));
    const error = document.createElement("p");
    error.className = "error";
    app.append(help, picker.field, error, actions);
  };

  const renderBottle = () => {
    const help = document.createElement("p");
    help.className = "help";
    help.textContent = config.help;
    const grid = document.createElement("div");
    grid.className = "milk-grid";
    config.milk_types.forEach((type) => {
      const entry = config.bottle_entries[type] || {};
      const card = document.createElement("section");
      card.className = "milk-card";
      card.dataset.milkType = type;
      const title = document.createElement("div");
      title.className = "milk-title";
      title.innerHTML = `<b>${type}</b><span>${type === "FOR" ? "Formula" : "Expressed breast milk"}</span>`;
      const fields = document.createElement("div");
      fields.className = "milk-fields";
      const amount = makeSelect("Amount", config.values, "ml", entry.value, "None");
      const duration = makeSelect("Duration", config.duration_values, "min", entry.duration, "None");
      amount.select.dataset.role = "amount";
      duration.select.dataset.role = "duration";
      fields.append(amount.field, duration.field);
      card.append(title, fields);
      grid.appendChild(card);
    });
    const error = document.createElement("p");
    error.className = "error";
    const actions = document.createElement("div");
    actions.className = "actions three";
    actions.innerHTML = '<button type="button" class="primary" data-action="save">Save feeds</button><button type="button" data-action="clear">Clear all</button><button type="button" data-action="cancel">Cancel</button>';
    actions.querySelector('[data-action="save"]').addEventListener("click", () => {
      const feeds = {};
      let invalid = false;
      grid.querySelectorAll(".milk-card").forEach((card) => {
        const amount = card.querySelector('[data-role="amount"]').value;
        const duration = card.querySelector('[data-role="duration"]').value;
        if ((amount && !duration) || (!amount && duration)) invalid = true;
        feeds[card.dataset.milkType] = amount && duration
          ? { amount: Number(amount), duration: Number(duration) }
          : null;
      });
      if (invalid) {
        showError("Choose both amount and duration for each feed.");
        return;
      }
      actions.querySelectorAll("button").forEach((button) => { button.disabled = true; });
      send("save", { feeds });
    });
    actions.querySelector('[data-action="clear"]').addEventListener("click", () => {
      grid.querySelectorAll("select").forEach((select) => { select.value = ""; });
      app.querySelector(".error").style.display = "none";
    });
    actions.querySelector('[data-action="cancel"]').addEventListener("click", () => send("cancel"));
    app.append(help, grid, error, actions);
  };

  app.replaceChildren();
  if (config.is_bottle) renderBottle();
  else renderBreast();
}
