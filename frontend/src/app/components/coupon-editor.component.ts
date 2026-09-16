import { Component, effect, inject, output, signal } from "@angular/core";
import { FormsModule, NgForm } from "@angular/forms";
import { Store } from "../store";
import { Coupon, CouponMatch, OUTCOMES } from "../models";

@Component({
  selector: "app-coupon-editor",
  standalone: true,
  imports: [FormsModule],
  template: `
    @if (draft; as coupon) {
      <form #editor="ngForm" class="panel editor" (ngSubmit)="submit(editor)">
        <div class="section-line">
          <div>
            <p class="eyebrow">KUPONGUNDERLAG</p>
            <h2>Matcher, odds och Svenska Folket</h2>
          </div>
          <button type="button" (click)="blank()">Ny tom kupong</button>
        </div>
        <p class="muted">
          Fyll i 13 matcher. Svenska Folket anges i procent, odds som
          decimalodds. Alla prognoser hämtas från API:t.
        </p>
        @if (coupon.demo) {
          <p class="notice">
            DEMO DATA · Matcherna, oddsen och strecken är exempel. Redigering
            behåller demomärkningen. Välj ”Ny tom kupong” för en egen kupong.
          </p>
        }
        @if (coupon.drawNumber) {
          <p class="notice">
            Redigering här skapar en manuell kopia. För att behålla
            livekopplingen och bara ändra odds, använd ”Underlag, lagmappning
            och manuella odds” ovan.
          </p>
        }
        <div class="editor-meta">
          <label
            >Vecka<input
              type="number"
              name="week"
              required
              min="1"
              max="53"
              [(ngModel)]="coupon.week" /></label
          ><label
            >Kupongdatum<input
              type="date"
              name="couponDate"
              required
              [(ngModel)]="coupon.date"
              (change)="setDates()"
          /></label>
        </div>
        <datalist id="team-options">
          @for (team of teams(); track team.id) {
            <option [value]="team.name"></option>
          }
        </datalist>
        @for (match of coupon.matches; track match.number) {
          <fieldset class="editor-match">
            <legend>Match {{ match.number }}</legend>
            <div class="fixture-inputs">
              <label
                >Hemmalag<input
                  [name]="'home-' + match.number"
                  required
                  maxlength="100"
                  [(ngModel)]="match.homeTeam"
                  list="team-options"
                  (input)="search(match.homeTeam)"
                  autocomplete="off"
              /></label>
              <label
                >Bortalag<input
                  [name]="'away-' + match.number"
                  required
                  maxlength="100"
                  [(ngModel)]="match.awayTeam"
                  list="team-options"
                  (input)="search(match.awayTeam)"
                  autocomplete="off"
              /></label>
              <label
                >Liga<select
                  [name]="'league-' + match.number"
                  [(ngModel)]="match.league"
                >
                  @for (league of leagues; track league.key) {
                    <option [value]="league.key">{{ league.label }}</option>
                  }
                </select></label
              >
              <label
                >Matchdatum<input
                  type="date"
                  required
                  [name]="'date-' + match.number"
                  [(ngModel)]="match.date"
              /></label>
            </div>
            <div class="odds-crowd-inputs">
              <div class="input-triplet">
                <span>Marknadsodds</span>
                @for (outcome of outcomes; track outcome.key) {
                  <label
                    >{{ outcome.sign
                    }}<input
                      type="number"
                      required
                      min="1.01"
                      max="10000"
                      step="0.01"
                      [name]="'odds-' + match.number + '-' + outcome.key"
                      [attr.aria-label]="
                        'Match ' + match.number + ', odds ' + outcome.sign
                      "
                      [(ngModel)]="match.marketOdds[outcome.key]"
                  /></label>
                }
              </div>
              <div class="input-triplet">
                <span>Svenska Folket (%)</span>
                @for (outcome of outcomes; track outcome.key) {
                  <label
                    >{{ outcome.sign
                    }}<input
                      type="number"
                      required
                      min="0"
                      max="100"
                      step="0.1"
                      [name]="'crowd-' + match.number + '-' + outcome.key"
                      [attr.aria-label]="
                        'Match ' + match.number + ', Folket ' + outcome.sign
                      "
                      [(ngModel)]="match.crowd[outcome.key]"
                  /></label>
                }
              </div>
            </div>
            @if (crowdError(match)) {
              <p class="field-error" role="status">{{ crowdError(match) }}</p>
            }
          </fieldset>
        }
        @if (error()) {
          <p class="notice error" role="alert">{{ error() }}</p>
        }
        <div class="editor-actions">
          <button class="primary" type="submit" [disabled]="store.loading()">
            {{
              store.loading() ? "Analyserar…" : "Analysera och generera system"
            }}</button
          ><button type="button" (click)="closed.emit()">
            Stäng redigering
          </button>
        </div>
      </form>
    }
  `,
})
export class CouponEditorComponent {
  readonly store = inject(Store);
  readonly closed = output<void>();
  readonly outcomes = OUTCOMES;
  readonly error = signal("");
  readonly teams = signal<{ id: string; name: string }[]>([]);
  readonly leagues = [
    { key: "E0", label: "Premier League" },
    { key: "E1", label: "Championship" },
    { key: "E2", label: "League One" },
  ];
  draft: Coupon | null = null;
  private searchVersion = 0;
  constructor() {
    effect(() => {
      this.draft = structuredClone(this.store.coupon());
    });
  }
  blank(): void {
    const date =
      this.store.coupon()?.date ?? new Date().toISOString().slice(0, 10);
    this.draft = {
      id: "manual-" + Date.now(),
      week: this.store.coupon()?.week ?? 1,
      date,
      demo: false,
      matches: Array.from({ length: 13 }, (_, i) => ({
        number: i + 1,
        homeTeam: "",
        awayTeam: "",
        league: "E0",
        date,
        marketOdds: { home: 0, draw: 0, away: 0 },
        crowd: { home: 0, draw: 0, away: 0 },
      })),
    };
  }
  setDates(): void {
    if (this.draft)
      for (const match of this.draft.matches) match.date = this.draft.date;
  }
  crowdError(match: CouponMatch): string {
    const sum =
      Number(match.crowd.home) +
      Number(match.crowd.draw) +
      Number(match.crowd.away);
    return Math.abs(sum - 100) > (this.store.config()?.crowdTolerance ?? 1)
      ? `Folket summerar till ${sum.toFixed(1)}%. Summan ska vara 100% (±1).`
      : "";
  }
  async search(query: string): Promise<void> {
    const version = ++this.searchVersion;
    try {
      const results = await this.store.searchTeams(query);
      if (version === this.searchVersion) this.teams.set(results);
    } catch {
      this.teams.set([]);
    }
  }
  async submit(form: NgForm): Promise<void> {
    if (!this.draft) return;
    if (form.invalid || this.draft.matches.some((m) => this.crowdError(m))) {
      this.error.set(
        "Kontrollera lagnamn, datum, alla odds och Svenska Folkets summor.",
      );
      form.control.markAllAsTouched();
      return;
    }
    this.error.set("");
    const coupon = structuredClone(this.draft);
    if (coupon.drawNumber) {
      coupon.id = "manual-" + Date.now();
      coupon.drawNumber = null;
      coupon.salesCloseAt = null;
      coupon.retrievedAt = null;
      coupon.dataSource = "manual";
      coupon.drawStatus = null;
      for (const match of coupon.matches) {
        match.providerEventId = null;
        match.crowdMatchId = null;
      }
    }
    const recorded_at = new Date().toISOString();
    for (const match of coupon.matches) {
      match.oddsSnapshot = {
        source: coupon.demo ? "demo_manual" : "manual",
        recorded_at,
      };
      match.crowdSnapshot = {
        source: coupon.demo ? "demo_manual" : "manual",
        recorded_at,
      };
    }
    await this.store.analyze(coupon);
    if (!this.store.error()) this.closed.emit();
  }
}
