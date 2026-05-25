class ContentLoaderController extends window.StimulusModule.Controller {
    static classes = [ "loading" ];
    static values = { url: String };

    connect() {
        this.requestId = 0;
        this.abortController = null;
        this.load();
    }

    disconnect() {
        this.abortActiveRequest();
    }

    dispatchLoaded(json) {
        this.dispatch("loaded", { detail: { json: json }});
    }

    dispatchFailed(error) {
        this.dispatch("failed", {
            detail: {
                error: error,
                message: error instanceof Error ? error.message : String(error),
            },
        });
    }

    abortActiveRequest() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    }

    async fetchJson(signal) {
        if (!this.urlValue) {
            throw new Error("Missing URL");
        }

        const response = await fetch(this.urlValue, { signal: signal });
        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }

        return response.json();
    }

    async load() {
        const currentRequestId = ++this.requestId;
        this.abortActiveRequest();
        this.abortController = new AbortController();

        const loadingTimeout = setTimeout(() => {
            if (currentRequestId === this.requestId) {
                this.element.classList.add(this.loadingClass);
            }
        }, 500);
        try {
            const json = await this.fetchJson(this.abortController.signal);

            if (currentRequestId !== this.requestId) {
                return;
            }

            this.dispatchLoaded(json);
        } catch (error) {
            if (error instanceof DOMException && error.name === "AbortError") {
                return;
            }
            this.dispatchFailed(error);
        } finally {
            clearTimeout(loadingTimeout);
            if (currentRequestId === this.requestId) {
                this.element.classList.remove(this.loadingClass);
            }
        }
    }
}

window.wagtail.app.register("content-loader", ContentLoaderController);