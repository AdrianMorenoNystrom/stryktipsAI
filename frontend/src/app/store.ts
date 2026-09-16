import { computed, inject, Injectable, signal } from "@angular/core";
import { HttpClient, HttpErrorResponse } from "@angular/common/http";
import { firstValueFrom } from "rxjs";
import {
  Analysis,
  AppConfig,
  Coupon,
  MatchAnalysis,
  Mode,
  ModelStatus,
  Sign,
  SystemCost,
  LiveState,
} from "./models";
import { deployment } from "../deployment";

@Injectable({ providedIn: "root" })
export class Store {
  readonly production = deployment.production;
  private readonly http = inject(HttpClient);
  readonly config = signal<AppConfig | null>(null);
  readonly status = signal<ModelStatus | null>(null);
  readonly coupon = signal<Coupon | null>(null);
  readonly analysis = signal<Analysis | null>(null);
  readonly loading = signal(false);
  readonly error = signal("");
  readonly notice = signal("");
  readonly live = signal<LiveState | null>(null);
  readonly dataMode = signal<"live" | "manual" | "demo">("live");
  readonly budget = signal(256);
  readonly mode = signal<Mode>("optimal");
  readonly selectedMatch = signal<MatchAnalysis | null>(null);
  readonly selections = signal<Sign[][]>([]);
  readonly manualCost = signal<SystemCost | null>(null);
  readonly costPending = signal(false);
  readonly modified = computed(
    () =>
      JSON.stringify(this.selections()) !==
      JSON.stringify(this.analysis()?.system.selections ?? []),
  );
  readonly fallbackCount = computed(
    () =>
      this.analysis()?.matches.filter((m) => m.source === "market_fallback")
        .length ?? 0,
  );
  private generation = 0;
  private costGeneration = 0;

  probabilityLabel(match: MatchAnalysis): string {
    return match.source === "ml"
      ? "Modell"
      : match.source === "market_baseline"
        ? "Marknad (aktiv)"
        : "Marknadsfallback";
  }

  oneIn(probability: number): number | null {
    return probability > 0 ? Math.round(1 / probability) : null;
  }

  async initialize(): Promise<void> {
    this.loading.set(true);
    try {
      const config = await firstValueFrom(
        this.http.get<AppConfig>("/api/config"),
      );
      this.config.set(config);
      await this.loadCurrent();
    } catch (error) {
      this.error.set(this.message(error));
      this.loading.set(false);
    }
  }

  async loadCurrent(drawNumber?: number, refresh = false): Promise<void> {
    const version = ++this.generation;
    this.loading.set(true);
    this.error.set("");
    const suffix = drawNumber ? `?draw_number=${drawNumber}` : "";
    try {
      const state = await firstValueFrom(
        refresh
          ? this.http.post<LiveState>(
              "/api/coupon/current/refresh" + suffix,
              {},
            )
          : this.http.get<LiveState>("/api/coupon/current" + suffix),
      );
      if (version !== this.generation) return;
      this.live.set(state);
      if (!state.draw) {
        if (this.production) {
          this.coupon.set(null);
          this.analysis.set(null);
          this.loading.set(false);
          this.notice.set(
            "Ingen aktuell kupong finns tillgänglig. Försök uppdatera senare.",
          );
          return;
        }
        await this.loadDemo(state.message ?? "Ingen aktuell kupong finns.");
        return;
      }
      this.dataMode.set("live");
      this.coupon.set(state.coupon);
      this.analysis.set(null);
      this.reset();
      this.selectedMatch.set(null);
      if (state.analysis_ready && state.coupon)
        await this.analyze(state.coupon);
      else this.loading.set(false);
    } catch (error) {
      if (version === this.generation) {
        this.error.set(this.message(error));
        this.loading.set(false);
      }
    }
  }

  async loadDemo(message = ""): Promise<void> {
    if (this.production) return;
    this.dataMode.set("demo");
    try {
      const coupon = await firstValueFrom(
        this.http.get<Coupon>("/api/coupon/demo"),
      );
      this.analysis.set(null);
      this.coupon.set(coupon);
      await this.analyze(coupon);
      this.notice.set(message);
    } catch (error) {
      this.error.set(this.message(error));
      this.loading.set(false);
    }
  }

  async analyze(coupon = this.coupon()): Promise<void> {
    if (!coupon) return;
    const version = ++this.generation;
    this.loading.set(true);
    this.error.set("");
    this.notice.set("");
    try {
      const result = await firstValueFrom(
        this.http.post<Analysis>("/api/coupon/analyze", {
          coupon,
          budget: this.budget(),
          mode: this.mode(),
        }),
      );
      if (version !== this.generation) return;
      this.coupon.set(structuredClone(result.inputCoupon ?? coupon));
      if (result.drawSnapshot && result.inputCoupon && this.live()) {
        this.live.update((state) =>
          state
            ? {
                ...state,
                draw: result.drawSnapshot!,
                coupon: result.inputCoupon!,
                movement: result.movement,
              }
            : state,
        );
      }
      this.dataMode.set(
        coupon.drawNumber ? "live" : coupon.demo ? "demo" : "manual",
      );
      this.analysis.set(result);
      this.reset();
      this.selectedMatch.set(null);
    } catch (error) {
      if (version === this.generation) this.error.set(this.message(error));
    } finally {
      if (version === this.generation) this.loading.set(false);
    }
  }

  setBudget(value: number): void {
    if (
      !Number.isFinite(value) ||
      value < (this.config()?.costPerRow ?? 1) ||
      value > 1000000
    ) {
      this.error.set(
        "Ange en budget mellan priset för en rad och 1 000 000 kr.",
      );
      return;
    }
    this.budget.set(value);
    void this.analyze();
  }
  setMode(value: Mode): void {
    this.mode.set(value);
    void this.analyze();
  }
  reset(): void {
    this.costGeneration++;
    this.selections.set(
      structuredClone(this.analysis()?.system.selections ?? []),
    );
    this.manualCost.set(this.analysis()?.system ?? null);
    this.costPending.set(false);
  }
  async toggle(index: number, sign: Sign): Promise<void> {
    const rows = structuredClone(this.selections());
    const row = rows[index];
    if (row.includes(sign) && row.length === 1) return;
    rows[index] = (["1", "X", "2"] as Sign[]).filter((s) =>
      s === sign ? !row.includes(s) : row.includes(s),
    );
    this.selections.set(rows);
    const version = ++this.costGeneration;
    this.costPending.set(true);
    try {
      const cost = await firstValueFrom(
        this.http.post<SystemCost>("/api/coupon/cost", { selections: rows }),
      );
      if (version === this.costGeneration) this.manualCost.set(cost);
    } catch (error) {
      if (version === this.costGeneration) {
        this.manualCost.set(null);
        this.error.set(this.message(error));
      }
    } finally {
      if (version === this.costGeneration) this.costPending.set(false);
    }
  }
  async copy(): Promise<void> {
    const coupon = this.coupon();
    if (!coupon) return;
    const text =
      `${coupon.demo ? "DEMO DATA · " : coupon.drawNumber ? "LIVE DATA · " : "MANUELL · "}Stryktipset · ${coupon.drawNumber ? "omgång " + coupon.drawNumber : "vecka " + coupon.week}\n` +
      coupon.matches
        .map(
          (m, i) =>
            `${m.number}. ${m.homeTeam} – ${m.awayTeam}: ${this.selections()[i].join("")}`,
        )
        .join("\n") +
      `\n${this.manualCost()?.rowCount} rader · ${this.manualCost()?.cost} kr`;
    try {
      await navigator.clipboard.writeText(text);
      this.notice.set("Systemet har kopierats.");
    } catch {
      this.error.set(
        "Webbläsaren kunde inte kopiera. Tillåt åtkomst till urklipp.",
      );
    }
  }
  message(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const body = error.error as {
        message?: string;
        errors?: { field: string; message: string }[];
        detail?: string;
      };
      if (error.status === 422)
        return (
          body.detail ??
          ((body.errors ?? [])
            .map((e) => `${e.field}: ${e.message}`)
            .join(" · ") ||
            body.message ||
            "Underlaget är inte redo för analys.")
        );
      return "Datan kunde inte hämtas just nu. Försök igen om en stund.";
    }
    return "Ett oväntat fel uppstod. Försök igen.";
  }
  async searchTeams(q: string): Promise<{ id: string; name: string }[]> {
    return firstValueFrom(
      this.http.get<{ id: string; name: string }[]>("/api/teams/search", {
        params: { q },
      }),
    );
  }
  async loadModelStatus(): Promise<void> {
    if (this.status()) return;
    try {
      this.status.set(
        await firstValueFrom(this.http.get<ModelStatus>("/api/model/status")),
      );
    } catch {
      this.notice.set("Fördjupad modellinformation kunde inte hämtas.");
    }
  }
  marketLabel(match: MatchAnalysis): string {
    return (
      (
        {
          bookmaker_consensus: "Flera bookmakers",
          cached_consensus: "Sparad bookmakerkonsensus",
          svenska_spel_odds: "Svenska Spels odds · fallback",
          manual: "Manuella odds · fallback",
        } as Record<string, string>
      )[match.marketSource ?? ""] ??
      (this.dataMode() === "demo" ? "Exempelodds" : "Marknadsdata")
    );
  }
}
