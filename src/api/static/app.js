(function () {
  "use strict";

  let accessToken = null;
  let currentRole = null;

  const el = (id) => document.getElementById(id);

  function showDashboard() {
    el("login-screen").hidden = true;
    el("dashboard-screen").hidden = false;
    el("topbar").hidden = false;
    el("user-role-badge").textContent = currentRole;
    el("admin-card").hidden = currentRole !== "admin";
  }

  function showLogin() {
    accessToken = null;
    currentRole = null;
    el("login-screen").hidden = false;
    el("dashboard-screen").hidden = true;
    el("topbar").hidden = true;
    el("result-card").hidden = true;
    el("model-info-content").innerHTML = "";
    el("login-form").reset();
  }

  async function authFetch(path, options) {
    options = options || {};
    options.headers = Object.assign({}, options.headers, {
      Authorization: "Bearer " + accessToken,
    });
    const response = await fetch(path, options);
    if (response.status === 401) {
      showLogin();
      el("login-error").hidden = false;
      el("login-error").textContent = "Session expirée, merci de te reconnecter.";
      throw new Error("Session expirée");
    }
    return response;
  }

  el("login-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    el("login-error").hidden = true;

    const body = new URLSearchParams();
    body.set("username", el("username").value);
    body.set("password", el("password").value);

    try {
      const response = await fetch("/token", { method: "POST", body });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Identifiants incorrects.");
      }
      const data = await response.json();
      accessToken = data.access_token;
      currentRole = el("username").value.trim().toLowerCase() === "admin" ? "admin" : "user";
      showDashboard();
    } catch (err) {
      el("login-error").textContent = err.message;
      el("login-error").hidden = false;
    }
  });

  el("logout-btn").addEventListener("click", showLogin);

  el("predict-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    el("predict-error").hidden = true;
    el("result-card").hidden = true;

    const payload = {
      anciennete_contrat_mois: Number(el("anciennete").value),
      nb_sinistres_12m: Number(el("sinistres").value),
      montant_total_sinistres: Number(el("montant").value),
      nb_paiements_retard: Number(el("retards").value),
      age_client: Number(el("age").value),
      prime_annuelle: Number(el("prime").value),
    };

    const button = el("predict-btn");
    button.disabled = true;
    button.textContent = "Calcul en cours…";

    try {
      const response = await authFetch("/predict/risk-client", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errPayload = await response.json().catch(() => ({}));
        throw new Error(errPayload.detail || "Erreur lors de la prédiction.");
      }
      const result = await response.json();
      const badge = el("risk-badge");
      badge.textContent = result.risque_eleve ? "Risque élevé" : "Risque faible";
      badge.className = "badge badge-lg " + (result.risque_eleve ? "badge-danger" : "badge-success");
      el("risk-proba").textContent = Math.round(result.probabilite_risque * 100) + " %";
      el("result-card").hidden = false;
    } catch (err) {
      el("predict-error").textContent = err.message;
      el("predict-error").hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = "Prédire le risque";
    }
  });

  el("model-info-btn").addEventListener("click", async function () {
    const content = el("model-info-content");
    content.innerHTML = "Chargement…";
    try {
      const response = await authFetch("/admin/model-info");
      if (!response.ok) {
        throw new Error("Accès refusé ou modèle indisponible.");
      }
      const data = await response.json();
      const rows = Object.entries(data.feature_importances)
        .sort((a, b) => b[1] - a[1])
        .map(
          ([name, value]) =>
            "<tr><td>" + name + "</td><td>" + (value * 100).toFixed(1) + " %</td></tr>"
        )
        .join("");
      content.innerHTML =
        "<p style='margin:0 0 8px;color:var(--ink-soft);'>Nombre d'arbres : " +
        data.n_estimators +
        "</p><table>" +
        rows +
        "</table>";
    } catch (err) {
      content.innerHTML = "<span style='color:var(--danger);'>" + err.message + "</span>";
    }
  });
})();
