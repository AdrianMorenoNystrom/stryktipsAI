import { Component, inject } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { Store } from "../store";
import { HeroComponent } from "../components/hero.component";
import { ProbabilitiesComponent } from "../components/probabilities.component";

@Component({
  standalone: true,
  imports: [DecimalPipe, HeroComponent, ProbabilitiesComponent],
  template: `
    <app-hero />
    <details class="how-it-works">
      <summary>Så fungerar sidan</summary>
      <p>1 betyder hemmaseger, X oavgjort och 2 bortaseger.</p>
      <p>
        Vi uppskattar sannolikheten för 1/X/2, jämför med Svenska Folket och
        väljer spikar och garderingar inom din budget.
      </p>
      <details>
        <summary>Hur fungerar modellen?</summary>
        <p>
          Den aktiva modellen utgår från bookmakerkonsensus när sådan finns.
          Saknas den används tydligt märkta sparade eller enskilda odds.
          Historiska modellvarianter har ännu inte visat stabil förbättring och
          används därför inte i liveprognosen.
        </p>
      </details>
      <p>
        <strong>Överstreckad</strong> betyder att folket valt tecknet oftare än
        vår sannolikhet motiverar. <strong>Understreckad</strong> betyder att
        vår sannolikhet är högre än folkets streck.
      </p>
      <p>
        Spelvärde jämför dessa andelar. Det är inte samma sak som garanterad
        ekonomisk avkastning.
      </p>
    </details>
    @if (store.analysis(); as analysis) {
      <div class="section-heading">
        <h2>Veckans insikter</h2>
      </div>
      <section class="insights" aria-label="Veckans tre insikter">
        @for (insight of analysis.insights; track insight.title) {
          <button
            class="insight-card"
            (click)="
              store.selectedMatch.set(analysis.matches[insight.number - 1])
            "
          >
            <span class="eyebrow">{{ insight.title }}</span>
            <div class="insight-title">
              <strong>{{
                insight.sign === "1"
                  ? insight.homeTeam
                  : insight.sign === "2"
                    ? insight.awayTeam
                    : insight.homeTeam + " – " + insight.awayTeam
              }}</strong
              ><span class="mini-sign">{{ insight.sign }}</span>
            </div>
            <span class="insight-numbers"
              >Vår sannolikhet <b>{{ insight.model * 100 | number: "1.0-0" }}%</b
              ><span
                >Folket {{ insight.crowd * 100 | number: "1.0-0" }}%</span
              ></span
            >
            <p class="small">{{ insight.description }}</p>
            <span class="small muted"
              >Match {{ insight.number }}
              <span aria-hidden="true">→</span></span
            >
          </button>
        }
      </section>
      <div class="section-heading">
        <h2>13 matcher. Hela bilden.</h2>
        <span class="muted">Öppna en match för att förstå valet</span>
      </div>
      <section class="match-grid">
        @for (match of analysis.matches; track match.number) {
          <article class="match-card panel">
            <div class="match-heading">
              <span class="match-number">{{ match.number }}</span>
              <h3>{{ match.homeTeam }} <span>–</span> {{ match.awayTeam }}</h3>
            </div>
            <app-probabilities
              label="Vår sannolikhet"
              [values]="match.model"
              [primary]="true"
            />
            <app-probabilities label="Svenska Folket" [values]="match.crowd" />
            @if (
              match.marketSource && match.marketSource !== "bookmaker_consensus"
            ) {
              <p class="small market-fallback">
                {{ store.marketLabel(match) }}
              </p>
            }
            <div class="match-footer">
              <span
                >Rekommendation
                <b class="recommendation">{{
                  match.recommendation.join("")
                }}</b></span
              ><button
                class="text-button"
                (click)="store.selectedMatch.set(match)"
                [attr.aria-label]="
                  'Varför ' + match.homeTeam + ' mot ' + match.awayTeam
                "
              >
                Varför? <span aria-hidden="true">↗</span>
              </button>
            </div>
          </article>
        }
      </section>
    }
  `,
})
export class OverviewComponent {
  readonly store = inject(Store);
}
