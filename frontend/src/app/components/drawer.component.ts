import { DatePipe } from "../time";
import {
  AfterViewInit,
  Component,
  ElementRef,
  inject,
  input,
  OnDestroy,
  signal,
  viewChild,
} from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { MatchAnalysis, OUTCOMES } from "../models";
import { Store } from "../store";
import { ProbabilitiesComponent } from "./probabilities.component";
import { NewsComponent } from "./news.component";
import { MarketHistoryComponent } from "./market-history.component";

@Component({
  selector: "app-drawer",
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    ProbabilitiesComponent,
    NewsComponent,
    MarketHistoryComponent,
  ],
  template: `
    <dialog
      #dialog
      class="match-dialog"
      aria-labelledby="match-title"
      (close)="store.selectedMatch.set(null)"
      (click)="backdrop($event)"
    >
      <div class="drawer-header">
        <div>
          <p class="eyebrow">
            MATCH {{ match().number }} · {{ match().league }}
          </p>
          <h2 id="match-title">
            {{ match().homeTeam }}<br /><span class="muted"
              >mot {{ match().awayTeam }}</span
            >
          </h2>
        </div>
        <button
          class="close-button"
          aria-label="Stäng matchanalys"
          (click)="close()"
        >
          ✕
        </button>
      </div>
      <div class="drawer-tabs" role="tablist" aria-label="Matchdetaljer">
        @for (name of tabs; track name) {
          <button
            role="tab"
            [attr.aria-selected]="tab() === name"
            [id]="'tab-' + name"
            aria-controls="detail-panel"
            [class.active]="tab() === name"
            (click)="tab.set(name)"
          >
            {{ name }}
          </button>
        }
      </div>
      <div
        class="drawer-content"
        id="detail-panel"
        role="tabpanel"
        [attr.aria-labelledby]="'tab-' + tab()"
      >
        @for (warning of match().warnings; track warning) {
          <p class="notice warning">{{ warning }}</p>
        }
        @if (tab() === "Översikt") {
          <app-probabilities
            label="Vår sannolikhet"
            [values]="match().model"
            [primary]="true"
          />
          <app-probabilities label="Svenska Folket" [values]="match().crowd" />
          <app-probabilities
            [label]="store.marketLabel(match())"
            [values]="match().market"
          />
          <div class="explanation">
            <p class="eyebrow">
              REKOMMENDATION {{ match().recommendation.join("") }}
            </p>
            <p>{{ match().explanation }}</p>
          </div>
          <details>
            <summary>Fördjupa jämförelsen</summary>
            <dl class="comparison">
              <div>
                <dt>Mest sannolikt</dt>
                <dd>{{ match().mostLikely }}</dd>
              </div>
              <div>
                <dt>Högst värdeindex</dt>
                <dd>{{ match().bestValue }}</dd>
              </div>
            </dl>
            <table>
              <caption>
                Skillnad mot Svenska Folket
              </caption>
              <thead>
                <tr>
                  <th>Tecken</th>
                  <th>Edge (pp)</th>
                  <th>Värdeindex</th>
                </tr>
              </thead>
              <tbody>
                @for (outcome of outcomes; track outcome.key) {
                  <tr>
                    <th>{{ outcome.sign }}</th>
                    <td>
                      {{ match().edge[outcome.key] > 0 ? "+" : ""
                      }}{{ match().edge[outcome.key] * 100 | number: "1.1-1" }}
                    </td>
                    <td>{{ match().value[outcome.key] | number: "1.2-2" }}</td>
                  </tr>
                }
              </tbody>
            </table>
            @if (match().valueFloorApplied) {
              <p class="small muted">
                Vid streck under 0,5% används ett golv på 0,5% för värdeindex.
              </p>
            }
            <p class="small muted">
              Odds: {{ match().oddsSnapshot?.source ?? "manual" }} · Folket:
              {{ match().crowdSnapshot?.source ?? "manual" }}. Marknadsodds är
              marginalrensade.
            </p>
          </details>
        }
        @if (tab() === "Data") {
          <p>
            Oddskälla: {{ store.marketLabel(match()) }}. Bookmakers:
            {{ match().marketQuality?.bookmaker_count ?? 0 }}.
          </p>
          <p>
            Observerade odds 1/X/2: {{ match().marketOdds.home }} /
            {{ match().marketOdds.draw }} / {{ match().marketOdds.away }}.
          </p>
          <p class="small">
            Marknad hämtad
            {{ match().oddsSnapshot?.retrieved_at | date: "dd/MM HH:mm" }}.
            Svenska Folket
            {{ match().crowdSnapshot?.retrieved_at | date: "dd/MM HH:mm" }}.
          </p>
          <p class="muted">
            Senaste fem spelade matcher före prognosen. Senaste matchen visas
            sist.
          </p>
          @for (side of sides; track side) {
            <h3>{{ side === "home" ? match().homeTeam : match().awayTeam }}</h3>
            @if (match().form[side].length) {
              <div class="form-badges">
                @for (game of match().form[side]; track $index) {
                  <span
                    [class.win]="game.points === 3"
                    [attr.aria-label]="
                      game.points === 3
                        ? 'Vinst'
                        : game.points === 1
                          ? 'Oavgjort'
                          : 'Förlust'
                    "
                    >{{
                      game.points === 3 ? "V" : game.points === 1 ? "O" : "F"
                    }}</span
                  >
                }
              </div>
              <ul class="form-list">
                @for (game of match().form[side]; track $index) {
                  <li>
                    <span
                      >{{ game.date | date: "dd/MM" }} · {{ game.opponent }}
                      <small
                        >({{ game.venue === "home" ? "H" : "B" }})</small
                      ></span
                    ><strong
                      >{{ game.goals_for }}–{{ game.goals_against }}</strong
                    >
                  </li>
                }
              </ul>
            } @else {
              <p class="notice">
                Ingen tillgänglig formhistorik för denna prognos.
              </p>
            }
          }
        }
        @if (tab() === "Historik") {
          @if (store.analysis()?.drawNumber) {
            <app-market-history [number]="match().number" />
          } @else {
            <p>Ingen sparad livehistorik för den här kupongen.</p>
          }
        }
        @if (tab() === "Data") {
          <details class="advanced-news">
            <summary>Nyheter – befintligt underlag</summary>
            <app-match-news [match]="match()" />
          </details>
          <p class="notice">
            Aktiv prognos: {{ match().activeModel ?? "Model v1" }}. News
            Intelligence påverkar ännu inte modellens sannolikheter.
          </p>
          <h3>Underlaget bakom sannolikheten</h3>
          <p class="muted">
            Dessa är modellinputs, inte uppmätta orsakseffekter.
          </p>
          <app-probabilities
            label="Market baseline"
            [values]="match().market"
          />
          @if (match().form.home.length) {
            <dl class="comparison">
              @for (factor of factors; track factor.key) {
                <div>
                  <dt>{{ factor.label }}</dt>
                  <dd>{{ feature(factor.key) | number: "1.1-1" }}</dd>
                </div>
              }
            </dl>
            <p class="small muted">
              Form avser tidigare matcher. Hemma/bortastyrka beräknas separat.
              Dessa historiska uppgifter visas även när marknadsbaselinen är
              aktiv; då korrigerar de inte prognosen.
            </p>
          } @else {
            <p class="notice">
              Marknaden är den enda prognoskällan för denna match. Se
              förklaringen ovan.
            </p>
          }
        }
      </div>
    </dialog>
  `,
})
export class DrawerComponent implements AfterViewInit, OnDestroy {
  readonly store = inject(Store);
  readonly match = input.required<MatchAnalysis>();
  readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>("dialog");
  readonly tab = signal("Översikt");
  readonly tabs = ["Översikt", "Data", "Historik"];
  readonly outcomes = OUTCOMES;
  readonly sides = ["home", "away"] as const;
  readonly factors = [
    { key: "home_elo_before", label: "Hemmalagets Elo" },
    { key: "away_elo_before", label: "Bortalagets Elo" },
    { key: "elo_difference", label: "Elo-skillnad inkl. hemmaplansfördel" },
    { key: "home_points_avg_5", label: "Hemma · poäng/match, senaste 5" },
    { key: "away_points_avg_5", label: "Borta · poäng/match, senaste 5" },
    { key: "home_venue_points_avg_5", label: "Hemmalagets hemmaform (poäng)" },
    { key: "away_venue_points_avg_5", label: "Bortalagets bortaform (poäng)" },
    { key: "rest_difference", label: "Skillnad i vilodagar (hemma − borta)" },
  ];
  private previousFocus: HTMLElement | null = null;
  ngAfterViewInit(): void {
    this.previousFocus = document.activeElement as HTMLElement;
    this.dialog().nativeElement.showModal();
  }
  ngOnDestroy(): void {
    this.previousFocus?.focus();
  }
  close(): void {
    this.dialog().nativeElement.close();
  }
  backdrop(event: MouseEvent): void {
    if (event.target === this.dialog().nativeElement) {
      const r = this.dialog().nativeElement.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right) this.close();
    }
  }
  feature(key: string): number | null {
    const value = this.match().features[key];
    return typeof value === "number" ? value : null;
  }
}
