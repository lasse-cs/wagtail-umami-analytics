class AnalyticsMetricsController extends window.StimulusModule.Controller {
    static values = { paths: Array, referrers: Array, countries: Array };
    static targets = [ "pathsTableBody", "referrersTableBody", "countriesTableBody" ];

    updateMetrics(event) {
        const metrics = event.detail.json["metrics"];
        this.pathsValue = metrics["paths"];
        this.referrersValue = metrics["referrers"];
        this.countriesValue = metrics["countries"];
    }

    onFailure() {
        document.dispatchEvent(
            new CustomEvent('w-messages:add', {
                detail: { text: 'Failed to load metric data', type: 'error', clear: true },
            }),
        );
    }

    pathsValueChanged(value) {
        if (!this.hasPathsTableBodyTarget) return;
        this.updateMetricTable(this.pathsTableBodyTarget, value);
    }

    referrersValueChanged(value) {
        if (!this.hasReferrersTableBodyTarget) return;
        this.updateMetricTable(this.referrersTableBodyTarget, value);
    }

    countriesValueChanged(value) {
        if (!this.hasCountriesTableBodyTarget) return;
        this.updateMetricTable(this.countriesTableBodyTarget, value);
    }

    updateMetricTable(tableBodyEl, items) {
        tableBodyEl.textContent = "";
        if (items.length === 0) items.push({"x": "-", "y": "-"});
        items.forEach(item => tableBodyEl.appendChild(this.createRow(item)));
    }

    createRow(item) {
        const rowEl = document.createElement("tr");
        const pathEl = document.createElement("td");
        pathEl.textContent = item["x"];
        rowEl.appendChild(pathEl);

        const valueEl = document.createElement("td");
        valueEl.textContent = item["y"];
        rowEl.appendChild(valueEl);
        return rowEl;
    }
}

window.wagtail.app.register("analytics-metrics", AnalyticsMetricsController);