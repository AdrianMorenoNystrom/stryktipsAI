import { DatePipe } from "../time";
import { Component, inject, input, OnInit, signal } from "@angular/core";

import { HttpClient } from "@angular/common/http";
import { firstValueFrom } from "rxjs";
import { MatchAnalysis, MatchNews, NewsSignal, NewsSource } from "../models";
import { Store } from "../store";

@Component({
  selector: "app-match-news",
  standalone: true,
  imports: [DatePipe],
  template: `
    <div class="news-heading">
      <div>
        <p class="eyebrow">VIKTIGA SIGNALER</p>
        <h3>Nyhetsunderlag</h3>
      </div>
      <button (click)="update()" [disabled]="updating() || !news()?.configured">
        {{ updating() ? "Kontrollerar…" : "Uppdatera kupongens nyheter" }}
      </button>
    </div>
    <p class="notice">
      News Intelligence påverkar ännu inte modellens sannolikheter.
    </p>
    @if (loading()) {
      <div class="skeleton" aria-label="Hämtar nyheter"></div>
    }
    @if (error()) {
      <p class="notice warning" role="alert">{{ error() }}</p>
    }
    @if (news(); as data) {
      @if (!data.configured) {
        <p class="notice warning">{{ data.message }}</p>
      }
      @if (data.error) {
        <p class="notice warning">{{ data.error }}</p>
      }
      @if (data.stale) {
        <p class="notice warning">
          Underlaget är äldre än ett dygn. Kontrollera källornas datum.
        </p>
      }
      <p class="small muted">
        @if (data.last_checked_at) {
          Senast kontrollerad
          {{ data.last_checked_at | date: "yyyy-MM-dd HH:mm" }}
        } @else {
          Ingen hämtning har gjorts för denna match.
        }
        · {{ data.source_count }} källor
      </p>
      @if (data.extraction === "rules") {
        <p class="small muted">
          Begränsad regelbaserad extraktion. Fler relevanta uppgifter kan finnas
          i källorna.
        </p>
      }
      @for (signal of data.signals; track signal.id) {
        <article class="news-signal">
          <div class="section-line">
            <strong
              ><span aria-hidden="true">{{
                signal.direction === "positive"
                  ? "↑"
                  : signal.direction === "negative"
                    ? "↓"
                    : "→"
              }}</span>
              {{ signal.team }}</strong
            ><span class="tag">{{ signal.status_label }}</span>
          </div>
          <p>{{ signal.summary }}</p>
          <p class="small muted">
            {{ signal.source_count }} källor · Senast bekräftad
            {{ signal.last_confirmed_at | date: "dd/MM HH:mm" }}
          </p>
          <details>
            <summary>Visa källor och belägg</summary>
            <p class="small">
              Först rapporterad
              {{ signal.first_published_at | date: "dd/MM HH:mm" }} ·
              Registrerad {{ signal.recorded_at | date: "dd/MM HH:mm" }}
            </p>
            @if (signal.has_conflicting_reports) {
              <p class="small">
                Det finns tidigare eller motstridiga uppgifter. Den valda
                statusen följer källornas tid och officiell prioritet.
              </p>
            }
            <blockquote>{{ signal.evidence }}</blockquote>
            @for (source of sourcesFor(signal); track source.version_id) {
              <a
                class="news-source"
                [href]="source.url"
                target="_blank"
                rel="noopener noreferrer"
                ><strong>{{ source.publisher }}</strong
                ><span>{{ source.title }}</span
                ><small
                  >Publicerad {{ source.published_at | date: "dd/MM HH:mm" }} ·
                  Tier {{ source.source_tier }} ↗</small
                ></a
              >
            }
          </details>
        </article>
      } @empty {
        <div class="empty-state">
          <h3>Inga belagda signaler att visa</h3>
          <p>
            Inga konkreta uppgifter har kunnat extraheras. Det betyder inte att
            laget saknar skador eller andra förändringar.
          </p>
        </div>
      }
      <details>
        <summary>
          Visa alla {{ data.sources.length }} insamlade artiklar
        </summary>
        @for (source of data.sources; track source.version_id) {
          <a
            class="news-source"
            [href]="source.url"
            target="_blank"
            rel="noopener noreferrer"
            ><strong>{{ source.publisher }}</strong
            ><span>{{ source.title }}</span
            ><small
              >{{ source.published_at | date: "yyyy-MM-dd HH:mm" }} · Tier
              {{ source.source_tier }} ↗</small
            ></a
          >
        }
      </details>
    }
  `,
})
export class NewsComponent implements OnInit {
  readonly match = input.required<MatchAnalysis>();
  readonly store = inject(Store);
  private readonly http = inject(HttpClient);
  readonly news = signal<MatchNews | null>(null);
  readonly loading = signal(true);
  readonly updating = signal(false);
  readonly error = signal("");
  ngOnInit(): void {
    void this.load();
  }
  async load(): Promise<void> {
    try {
      this.news.set(
        await firstValueFrom(
          this.http.get<MatchNews>(`/api/matches/${this.match().matchId}/news`),
        ),
      );
    } catch {
      this.error.set(
        "Nyhetsunderlaget kunde inte hämtas. Matchprognosen påverkas inte.",
      );
    } finally {
      this.loading.set(false);
    }
  }
  async update(): Promise<void> {
    this.updating.set(true);
    this.error.set("");
    try {
      await firstValueFrom(
        this.http.post("/api/news/update", { coupon: this.store.coupon() }),
      );
      await this.load();
    } catch {
      this.error.set(
        "Nyhetsuppdateringen kunde inte slutföras. Senast sparad information visas.",
      );
    } finally {
      this.updating.set(false);
    }
  }
  sourcesFor(signal: NewsSignal): NewsSource[] {
    return (
      this.news()?.sources.filter((s) =>
        signal.source_article_ids.includes(s.version_id),
      ) ?? []
    );
  }
}
