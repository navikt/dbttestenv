# Introduksjon

`dbttestenv` er et generisk pytest-bibliotek for å kjøre enhetstester mot dbt-modeller i en Oracle testcontainer.

Biblioteket tilbyr:
- Automatisk oppstart og initialisering av en Oracle-database i Docker
- Synkronisering av database objekter i testcontaineren og deres python representasjon med DDL fra produksjonsdatabasen
- `testenv` CLI for å kontrollere testmiljø og kjøre dbt og pytest mot testcontaineren

Dette prosjektet ble splittet fra [dvh_ams](https://github.com/navikt/dvh_ams). Git historikk finnes i stien `dbt/unit_tests/dbttestenv`.

##  Quickstart

```bash
# Installer dbttestenv i ditt prosjekt
uv add --group dev "git+https://github.com/navikt/dbttestenv"

source .venv/bin/activate

testenv new        # todo: førstegangs konfigurasjon av prosjektet

testenv diagnose   # sjekk at miljøet er satt opp riktig
testenv init       # start og initialiser testcontaineren
testenv init --rm  # slett, start og initialiser testcontaineren
testenv dbt -- run # kjør dbt mot testdatabasen
testenv pytest     # kjør alle tester
testenv stop       # stopp containeren
```

# Innhold

- [Motivasjon](#motivasjon)
- [Oppsett av testmiljø](#oppsett-av-testmiljø)
- [Konfigurasjon](#konfigurasjon)
- [Initialiser kildeskjema og generer python-modeller](#initialiser-kildeskjema-og-generer-python-modeller)
- [Skriv tester](#skriv-tester)
- [Kjør testene](#kjør-testene)
- [Utvikling](#utvikling)
- [Teknisk implementering](#teknisk-implementering)
- [Feilsøking](#feilsøking)


# Motivasjon

Automatiserte enhetstester er et nyttig verktøy til kvalitetssikring og utvikling. De tar for seg en liten del av systemet, og tester at den fungerer som forventet.

Fordeler:
- Kan kjøres i CI/CD på hver commit, slik at feil oppdages tidlig.
- Testing på ren syntetisk data, kan kjøres lokalt. Bra for personvern og sikkerhet.
- Testbiliotekt vokser med tiden, og gir en dokumentasjon på hvordan systemet skal fungere.
- Endringer som ødelegger eldre funksjonalitet oppdages tidlig, og kan rettes før de når produksjon.
- Testing av grensetilfeller som ikke finnes i produksjonsdata.
- Utvikling med TDD (Test Driven Design) hvor man skriver tester først for endringen man utvikler.

Ulempen med dbt sin [unit tests](https://docs.getdbt.com/docs/build/unit-tests) er at de ikke er fleksible nok sammenlignet med det en test framework som [pytest](https://docs.pytest.org/en/stable/) kan tilby. Ved å bruke python for å teste blir det også mulig å lage klasser og funksjoner for å gjøre testkoden DRY (Don't Repeat Yourself) og bedre lesbart. Det er enklere å kunne skrive `lagre_arbeidssokerperiode(fk_person1, fra, til)` enn en `INSERT` statement som inneholder alle kolonnene i en eller flere tabeller.

## Konsept

Biblioteket bruker [testcontainers](https://testcontainers.com/) til å starte en Oracle-database i Docker
fra kode, før testene kjører.

Databasen initialiseres ved å opprette alle kildeskjemaer og kildetabeller som trengs for å kjøre testene. Definisjonene er del av din  kodebase som [sqlalchemy](https://www.sqlalchemy.org/) modeller. De genereres automatisk ved at en utvikler kjører et verktøy som leser SQL definisjonene i produksjonsdatabasen.

Som siste del av initialiseringen kjøres `dbt run` for å opprette alle dbt-modellene som skal testes.

Så kjøres hver test. Før hver test slettes alle rader i alle kildetabeller og dbt modeller, slik at testen kan opprette
et kjent utgangspunkt. Radene slettes ikke etter testen, slik at det er mulig å utforske databasen etter en test.

Testen oppretter rader i kildetabeller og leser fra dbt-modellene for å sjekke at de inneholder forventede data. Dbt trenges
ikke kjøres når transformasjoner er implementert som visning. For inkrementelle modeller kjøres `dbt run` for å
oppdatere modellene. Materialiserte visninger kan erstattes med en vanlig visning som optimering.

Så brukes [assert](https://docs.pytest.org/en/stable/assert.html) for å sjekke at resultatet er som forventet.

# Oppsett av testmiljø

## Github

Se https://github.com/navikt/dvh_ams/blob/main/.github/workflows/dbt_unit_tests.yml for hvordan testene kjøres i github actions. Det er en workflow som kjører på hver commit og pull request på _main_.

## Lokalt

Det er mye som kan gå galt i oppsett av uviklingsmiljø. Det finnes et hjelpeskript som sjekker for feil og gir tips for
å rette dem. Du trenger ikke ha installert noe bortsett fra python for å kjøre den, og du kan kjøre den når som helst:
```bash
python dbt/unit_tests/diagnose.py
```

Når du har satt opp `uv` og installert avhengighetene kan du også kjøre den med:
```bash
uv run testenv diagnose
# eller kortere:
source .venv/bin/activate
testenv diagnose
```

## Sandbox for agenter

Sett miljøvariablen `DBTTESTENV_NO_CONTAINER_MANAGEMENT=true` for å unngå all interaksjon med docker/colima/podman hvis mulig. Det gjør det mulig å la agenter kjøre `testenv` i en sandbox uten docker (f.eks. med Navs cplt). Kjør CLI kommandoer som bruker en container runtime utenfor sandbox (init, start, stop, remove).

### Første gang

Sjekk at du har `python` installert. Dersom du har installert python og `python --version` eller `pip --version`
feiler, kan du prøve `python3` eller `pip3` i stedet.

#### Mac
Installer [Colima](https://github.com/abiosoft/colima) og docker (ikke Docker Desktop):
```bash
brew install docker
brew install colima
```

Om du bruker vscode, sjekk at den er tilgjengelig i terminalen ved å sjekke at `which code` returnerer en sti. Hvis ikke,
følg denne instruksjonen: https://code.visualstudio.com/docs/setup/mac#_configure-the-path-with-vs-code

Oracle databasen bruker en del minne, så det kan være nødvendig å øke minnet til colima til 4GB
eller mer. Du vil i såfall ser at containeren crasher etter start. Du kan sjekke minnetilgangen med `colima list` .
For colima kan du også sette minnetilgang permanent med `colima start --edit` og
konfigurasjonen `memory: 4`. Når du endrer denne innstillingen husk å omstarte colima med `colima stop` og `colima start`.

På Mac må du sette en miljøvariabel før du kan kjøre testene:
```bash
export DOCKER_HOST=unix:///Users/youruser/.colima/default/docker.sock
```

Det kan du enten gjør hver gang du kjører testene, eller legge den linjenen i din `~/.bashrc`, `~/.zshrc` eller lignende.

Stien hvor `docker.sock` er lagret kan du finne ut med `colima status` kommandoen. Den endres ikke med mindre du
bruker flere colima profiler.

#### Windows
På Windows kan du bruke [Docker Desktop](https://www.docker.com/products/docker-desktop/) med lisens, eller
[Podman](https://podman.io/) som kan brukes uten lisens.

Begge bør ha mer enn 4GB minne tilgjengelig by default, men ta en dobbelsjekk fordi det kan føre til en crash av
containeren når den starter.

Du må eventuelt starte Docker eller Podman manuelt fra deres grafisk grensesnitt før du kjører testene.


#### Begge

Se om docker fungerer som forventet:
```bash
docker pull hello-world
docker run -it --rm hello-world
```

Du må også installere `uv`:
```bash
pip install --user uv
```

Om du får feil med "access denied" på Windows når du kjører `pip` eller `uv` er det nok Windows Defender som blokkerer
tilgangen. Legg inn et unntak til mappen hvor `pip` eller `uv` er installert (kjør `(Get-Command uv).Path` i PowerShell),
eller starte deres CLI som modul i stedet for som et program:

```bash
python -m pip install --user uv
```

Er prosjektet ditt allerede konfigurert er det bare å installer avhengighetene:
```bash
git clone https://github.com/navikt/my_project.git
cd my_project
uv sync
```

# Konfigurasjon

Last ned repository og konfigurer biblioteket:

```bash
git clone https://github.com/navikt/my_project.git
cd my_project

# Første gang du tar dbttestenv i bruk i ditt prosjekt
uv add --group dev "git+https://github.com/navikt/dbttestenv"
source .venv/bin/activate
testenv new        # todo
```

## pytest-plugin

`dbttestenv` registreres automatisk som en pytest-plugin når pakken er installert. Ingen endringer i pytest's `conftest.py` eller eksplisitt import er nødvendig.

Biblioteket trenger imidlertid en `TestenvConfig` fra det konsumerende prosjektet. Denne leveres via entry point
`dbttestenv.config` i ditt prosjekts `pyproject.toml`:

```toml
[project.entry-points."dbttestenv.config"]
mitt-prosjekt = "unit_tests.testenv_config:config"
```

Høyre side er en dotted import path til et Python-modul som eksponerer et `config`-attributt av typen `TestenvConfig`.

## TestenvConfig

Opprett en `testenv_config.py` i testmappen din, f.eks. i `dbt/unit_tests/testenv_config.py`:

```python
from pathlib import Path
from dbttestenv import TestenvConfig

_UNIT_TESTS_DIR = Path(__file__).parent

config = TestenvConfig(
    dbt_schema="mitt_skjema",
    dbt_project_path=_UNIT_TESTS_DIR.parent,
    models_output_dir=_UNIT_TESTS_DIR / "models" / "generated",
)
```

### Alle felter i TestenvConfig

| Felt | Type | Beskrivelse |
|---|---|---|
| `dbt_schema` | `str` | Navn på dbt-skjemaet (output-schema i databasen) |
| `dbt_project_path` | `Path` | Sti til dbt-prosjektmappen (inneholder `dbt_project.yml`) |
| `models_output_dir` | `Path` | Sti til mappen med genererte SQLAlchemy-modeller |
| `extra_schemas` | `list[str]` | Eventuelle ekstra skjemaer som skal opprettes |
| `init_sql_files` | `list[Path]` | SQL-filer som kjøres etter skjema-initialisering (f.eks. stored procedures) |
| `seed_sql_dir` | `Path \| None` | Mappe med SQL seed-filer som lastes ved teststart |
| `pre_testenv_setup` | `Callable[[Connection], None] \| None` | Hook: kjøres før alt annet |
| `post_testenv_setup` | `Callable[[Connection], None] \| None` | Hook: kjøres etter full initialisering |
| `pre_source_schema_init` | `Callable[[Connection], None] \| None` | Hook: kjøres før kildeskjemaer opprettes |
| `post_source_schema_init` | `Callable[[Connection], None] \| None` | Hook: kjøres etter kildeskjemaer er opprettet |
| `pre_dbt_init` | `Callable[[Connection], None] \| None` | Hook: kjøres før `dbt run` |
| `post_dbt_init` | `Callable[[Connection], None] \| None` | Hook: kjøres etter `dbt run` |

Eksempel med hooks og ekstra oppsett:

```python
from pathlib import Path
from sqlalchemy import Connection, text
from dbttestenv import TestenvConfig

_UNIT_TESTS_DIR = Path(__file__).parent
_DB_INSTALL_DIR = _UNIT_TESTS_DIR.parents[1] / "db" / "install"


def _post_source_schema_init(connection: Connection) -> None:
    sql = (_DB_INSTALL_DIR / "EXTRA_TABLE.DDL").read_text(encoding="utf-8")
    for statement in sql.split(";\n"):
        stmt = statement.strip("\n\r;")
        if stmt:
            connection.execute(text(stmt))


config = TestenvConfig(
    dbt_schema="mitt_skjema",
    dbt_project_path=_UNIT_TESTS_DIR.parent,
    models_output_dir=_UNIT_TESTS_DIR / "models" / "generated",
    extra_schemas=["annet_skjema"],
    init_sql_files=[
        _UNIT_TESTS_DIR / "utils" / "sql" / "mock_procedures.sql",
    ],
    seed_sql_dir=_UNIT_TESTS_DIR / "seeds",
    post_source_schema_init=_post_source_schema_init,
)
```

### Initialisering av konfigurasjon

dbttestenv initialiserer testcontaineren fra konfigurasjonen i følgende rekkefølge:
1. Oppretter kildeskjemaer og kildetabeller fra SQLAlchemy-modeller definert i `models_output_dir`
2. Kjører eventuelle `init_sql_files` (f.eks. stored procedures og mocks)
3. Kjører seed-SQL fra `seed_sql_dir`
4. Kjører `dbt run` for å opprette alle dbt-modeller


# Initialiser kildeskjema og generer python-modeller

`uv run model_generator` leser SQL definisjonene fra produksjonsdatabasen og genererer SQLAlchemy modeller for alle tabeller i kildeskjemaene og dbt-modellene. Skriptet kjøres i KNAST, deretter må endringene committes til git.

Skriptet må kjøres når det er endringer i kildetabeller eller dbt-modeller som kan føre til inkompatibilitet. I de fleste tilfeller vil testene feiler først, noe som man får med seg fra slack-varsling etter at workflowen har feilet. Test loggene vil da vise en SQL error som sier at en tabell eller kolonne ikke finnes.

`model_generation.yml` er konfigurasjonsfilen som spesifiserer hvilke tabeller som skal genereres. Når det er endringer i tabellnavn, eller når det skal legges til nye tabeller må den endres.  Det er også mulig å begrense hvilke kolonner man vil hente, man trenger f.eks. ofte ikke alle kolonner fra `dim_tid` eller `dim_person1`.

Eksempel:
```yaml
dbt_schema:
  name: dvh_ams
  dbt_models:
    - name: int_sokt_aap_perioder_arena
      unique: [fk_person1, gyldig_fom_dato]
    # ...
sources:
  - schema: dvh_ams
    objects:
      - name: raa_poaap_kelvin_bq_delta
        # alle kolonner

  - schema: dt_kodeverk
    objects:
      - name: dim_tid
        columns:
          - pk_dim_tid
          - dato
          - uke
          - aar_uke
          - aar

  - schema: dt_person
    objects:
      - name: dim_person1
        columns:
          - fk_person1
          - bosted_land
          - personstatus_kode
          - skjermet_kode
          - lastet_dato
          - kildesystem
          - gyldig_fra_dato
          - gyldig_til_dato
          - gyldig_flagg

      - name: ident_off_id_til_fk_person1
        # alle kolonner
```

For å oppdatere modellene, kjør følgende kommando i terminalen: \
(NB! dersom "error: Failed to spawn: model_generator" oppstår, kjør `uv sync` først)

```bash
uv run model_generator generate \
    --host=dmv03-scan.adeo.no \
    --port=1521 \
    --service-name=dwh_ro \
     --user=<ident>[DVH_AMS]
```

Da får man f.eks. dette modell generert:
```python
class IdentOffIdTilFkPerson1(Base):
    __tablename__ = 'ident_off_id_til_fk_person1'
    __table_args__ = {'schema': 'dt_person'}

    fk_person1: Mapped[float] = mapped_column(NUMBER(38, 0, False), nullable=False)
    off_id: .apped[str] = mapped_column(VARCHAR(30), nullable=False)
    skjermet_kode: Mapped[float] = mapped_column(NUMBER(1, 0, False), nullable=False)
    gyldig_fra_dato: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    gyldig_til_dato: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    gyldig_flagg: Mapped[float] = mapped_column(NUMBER(1, 0, False), nullable=False)
    pk_dummy: Mapped[float] = mapped_column(NUMBER(38, 0, False), Identity(), primary_key=True)
```

Tabellen blir automatisk opprettet når testcontaineren initialiseres.

Når man jobber lokalt og har endret en dbt modell som man ønsker å generere en sqlalchemy modell for:
```bash
uv run model_generator generate --testcontainer --models <dbt_schema>.<dbt_model>
```

# Skriv tester

dbttestenv starter testcontaineren automatisk som del av testoppsett. Har du konfigurasjonen på plass, er dette den enkelst mulige test:

```python
def test_noe(session):
    session.add(MinKildeTabell(id=1, navn="Test"))
    session.commit()
    # DB visninger transformerer instantant, ved inkrementelle modeller ville dbt kjøres her
    result = session.execute(select(StgMinKildeTabell)).scalars().all()
    assert len(result) == 1
    assert result[0].navn == "Test"
```

Det forutsetter at modellene er generert fra:
```yaml
dbt_schema:
  name: dbt_schema
  dbt_models:
    - name: stg_min_kilde_tabell
      unique: [id]
sources:
  - schema: kilde_schema
    objects:
      - name: min_kilde_tabell
```

## Eksempel på bruk

### Beste praksis: `ny_<modellnavn>`-funksjoner

Det anbefales å lage hjelpefunksjoner `ny_<modellnavn>(session, ...)` for å sette inn testdata. Disse fungerer
som en fabrikk med fornuftige standardverdier, slik at testene bare trenger å sette det som er relevant for
scenariet de tester. Det gjør testene kortere, lettere å lese og lettere å vedlikeholde.

```python
from datetime import datetime
from sqlalchemy.orm import Session
from dbttestenv.fakes import FakerFactory

from .models.generated.sources.mitt_skjema import MinTabell
from .models.generated.dbt_models import IntMinModell


def ny_min_tabell(
    session: Session,
    ff: FakerFactory,
    fom: datetime,
    tom: datetime | None = None,
    fk_person1: int = 1,
    status: str = "AKTIV",
) -> None:
    faker = ff.get("MinTabell")
    session.add(
        MinTabell(
            id=faker.unique.random_int(),
            fk_person1=fk_person1,
            gyldig_fom=fom,
            gyldig_tom=tom,
            status=status,
        )
    )
    session.commit()
```

Testene kan da se slik ut:

```python
from datetime import datetime
import sqlalchemy
from sqlalchemy import select
from dbttestenv.fakes import FakerFactory

from .models.generated.dbt_models import IntMinModell


def test_aktiv_bruker(session: sqlalchemy.orm.Session, ff: FakerFactory):
    """Brukeren er aktiv i dag"""
    ny_min_tabell(session, ff, fom=datetime(2024, 1, 1))

    result = session.execute(select(IntMinModell)).scalars().all()
    assert len(result) == 1
    assert result[0].status == "AKTIV"


def test_avsluttet_bruker(session: sqlalchemy.orm.Session, ff: FakerFactory):
    """Brukeren er avsluttet"""
    ny_min_tabell(session, ff, fom=datetime(2024, 1, 1), tom=datetime(2024, 6, 30), status="AVSLUTTET")

    result = session.execute(select(IntMinModell)).scalars().all()
    assert len(result) == 1
    assert result[0].status == "AVSLUTTET"
```

### Teste flere scenarier med klasse

Bruk en klasse med `session_class_scope` når du vil teste flere sider av samme scenario uten å sette opp
data på nytt for hver test:

```python
import pytest
import sqlalchemy
from sqlalchemy import select
from dbttestenv.fakes import FakerFactory

from .models.generated.dbt_models import IntMinModell


@pytest.mark.usefixtures("session_class_scope")
class TestPersoner:
    def test_setup(self, session_class_scope: sqlalchemy.orm.Session, ff: FakerFactory):
        ny_min_tabell(session_class_scope, ff, fom=datetime(2024, 1, 1), fk_person1=1)
        ny_min_tabell(session_class_scope, ff, fom=datetime(2024, 3, 1), fk_person1=2, status="AVSLUTTET")

    def test_antall_aktive(self, session_class_scope: sqlalchemy.orm.Session):
        result = session_class_scope.execute(
            select(IntMinModell).where(IntMinModell.status == "AKTIV")
        ).scalars().all()
        assert len(result) == 1

    def test_antall_avsluttede(self, session_class_scope: sqlalchemy.orm.Session):
        result = session_class_scope.execute(
            select(IntMinModell).where(IntMinModell.status == "AVSLUTTET")
        ).scalars().all()
        assert len(result) == 1
```
## Fixture API

Alle fixtures eksporteres automatisk av pluginen og er tilgjengelige i alle testfiler uten import.

### `testenv_config` — `TestenvConfig` (session scope)

Returnerer konfigurasjonen lastet fra prosjektets entry point. Brukes internt av andre fixtures, men kan også
injiseres direkte om nødvendig.

### `oracle_test_container` — `ConnectionConfig` (session scope)

Starter (eller gjenbruker) Oracle-testcontaineren og kjører full initialisering: oppretter skjemaer, kjører
init-SQL og kjører `dbt run`. Deles mellom alle tester i en pytest-sesjon.

### `connection` — `sqlalchemy.Connection` (function scope)

Åpner en databasetilkobling. **Alle rader i alle kilde- og dbt-tabeller slettes** før tilkoblingen leveres, slik
at hver test starter med et rent, kjent utgangspunkt. Tilkoblingen commites og lukkes etter testen.

```python
def test_noe(connection):
    connection.execute(text("INSERT INTO mitt_skjema.min_tabell ..."))
```

### `session` — `sqlalchemy.orm.Session` (function scope)

En SQLAlchemy ORM-session bygget på `connection`. Foretrekkes fremfor `connection` når man bruker genererte
SQLAlchemy-modeller.

```python
def test_noe(session):
    session.add(MinTabell(id=1, navn="Test"))
    session.commit()
```

### `connection_module_scope` / `session_module_scope` (module scope)

Samme som `connection`/`session`, men deles mellom alle tester i samme modul. Nyttig når testene i en fil
avhenger av hverandre eller det er dyrt å sette opp data på nytt.

### `connection_class_scope` / `session_class_scope` (class scope)

Samme som `connection`/`session`, men deles mellom alle tester i en testklasse.

### `ff` — `FakerFactory` (function scope)

Fabrikk for [Faker](https://faker.readthedocs.io/)-instanser seeded av et sekvens-navn. Gir reproduserbar
tilfeldig testdata: samme navn gir alltid samme sekvens av verdier.

```python
def test_noe(ff):
    faker = ff.get("MinTabell")
    pk = faker.unique.random_int()
    navn = faker.name()
```

# Kjør testene

Start din container server først (colima, docker eller podman). `colima start`, eller via grafisk grensesnitt med
pordman eller docker desktop.

På Mac må du eventuelt først kjøre `export DOCKER_HOST=...` hvis du ikke har lagt den i din `~/.bashrc` eller `~/.zshrc`.

Kjør enkelte tests:
```bash
# hvis ikke du allerede er i dvh_ams mappen, start der
cd dvh_ams
source .venv/bin/activate
testenv pytest -- -k test_navn
testenv pytest -- -k test_class
testenv pytest -- -k delstreng_av_test_navn
# Naviger til unit_tests mappen for å kjøre følgende kommandoer
testenv pytest -- test_fil.py
testenv pytest -- test_fil.py::test_func
testenv pytest -- test_fil.py::TestClass
testenv pytest -- test_fil.py::TestClass::test_method
```

Kjør alle tests:
```bash
testenv pytest
```

Som standard gjenbrukes en eksisterende container mellom kjøringer for å spare tid under utvikling.
Sett miljøvariabelen `DBTTESTENV_CLEANUP_CONTAINER=true` for å slette containeren automatisk etter testing.

# Utvikling

Ved endringer kun i dbt-modellen, uten å ville gjenopprette hele containeren:

```bash
testenv dbt -- run -s my_dbt_model
```

`testenv dbt` setter opp miljøvariabler slik at dbt peker på testcontaineren.

## Utvilking med agenter

Det er skrevet en testing skill i `.github/skills/dbt-testing`. NB at Nav krever at vi bruker en sandbox. `cplt` sandboxen (https://ki-utvikling.nav.no/cplt) har ikke tilgang til docker, så det er nødvendig å sette miljøvariabelen `DBTTESTENV_NO_CONTAINER_MANAGEMENT=true` for å unngå at testenv prøver å starte eller stoppe containeren.

Da er det nødvendig å kjøre `testenv init` og andre container management kommandoer manuelt utenfor sandboxen.

Se også `.github/skillts/dbt-testing/SKILL.md`.


## SQL Developer / IDE-tilkobling

Installer SQL developer extension i vscode, naviger til SQL developer iconet i fanen på høyresiden, høyreklikk på testcontainer og lag en ny tilkobling med følgende innstillinger:

| Felt | Verdi                                                            |
|---|------------------------------------------------------------------|
| Bruker | `system`                                                         |
| Passord | hent fra `.testcontainer_credentials` filen |
| Host | `localhost`                                                      |
| Port | `1521`                                                           |
| Service name | `FREEPDB1`                                                       |

Kildeskjemaer ligger under `Other Users` i databaseklienten.

`.testcontainer_credentials` genereres automatisk ved første kjøring av `testenv init` i prosjektmappe root.

# Teknisk implementering

## Testcontainer

[Testcontainers](https://testcontainers.com/) starter en Oracle-database i Docker fra kode. Den genererer
automatisk en bruker med tilfeldig passord. Passordet skrives til `.testcontainer_credentials` i
prosjektmappen slik at det kan brukes av dbt og databaseklienter.

Som standard gjenbrukes en eksisterende container mellom kjøringer for å spare tid under utvikling.
Sett miljøvariabelen `TESTENV_CLEANUP_CONTAINER=true` for å slette containeren automatisk etter testing.

## SQLAlchemy

Et ORM (Object Relational Mapper) bibliotek som lar deg definere databasemodeller som Python-klasser og
jobbe med rader som objekter.

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import NUMBER, VARCHAR
from typing import Optional


class Base(DeclarativeBase):
    pass


class MinTabell(Base):
    __tablename__ = "min_tabell"
    __table_args__ = {"schema": "mitt_skjema"}

    pk_min_tabell: Mapped[int] = mapped_column(NUMBER(38, 0, False), primary_key=True)
    navn: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
```

Skriv og les rader:

```python
# Skrive en ny rad
session.add(MinTabell(pk_min_tabell=1, navn="Test Navn"))
session.commit()

# Lese rader
rader = session.execute(
    select(MinTabell).order_by(MinTabell.navn)
).scalars().all()

assert len(rader) == 1
assert rader[0].navn == "Test Navn"
```

## Ytelsesoptimering

Unngå å kjøre `dbt run` unødvendig i tester, det tar for lang tid. Erstatt materialiserte visninger med
vanlige visninger under testing:

```sql
{{
    config(
        materialized=('materialized_view' if not var('unittesting', default=False) else 'view')
    )
}}
```

Variabelen `unittesting` settes til `True` av `dbttestenv` når dbt kjøres under initialisering av
testcontaineren.

En annen optimering er å teste flere scenarier i én test ved å bruke ulike `fk_person1`-verdier,
kombinert med en testklasse og `session_class_scope`.


# Feilsøking
## Utviklings- og testmiljø

Til feilsøking, start alltid med å kjøre:
```bash
python dbt/unit_tests/diagnose.py
# eller
source .venv/bin/activate
testenv diagnose
```

For å tømme alle tabeller og re-seede testdatabasen uten å fjerne containeren:

```bash
testenv clear
```

## Kjør SQL-spørringer

For å kjøre en SQL-spørring direkte mot testdatabasen:

```bash
testenv query "SELECT * FROM dvh_ams.min_tabell WHERE ROWNUM <= 10"
```

Output-format kan styres med `-f`/`--format`:
- `markdown` (default) — tabell i markdown-format
- `csv` — kommaseparert
- `json` — JSON-array av objekter

For eksempel:
```bash
testenv query -f json "SELECT * FROM dvh_ams.int_bosatt_i_norge WHERE ROWNUM <= 5"
```

For å slett containeren (f.eks. ved endringer i dbt-modell eller kildetabellene, slik at alt blir opprettet på nytt):
```bash
testenv remove
testenv init
# eller
testenv init --remove
```

Det hjelper av og til å omstarte docker/colima/podman.

## Feil i tester / modellen

Konfigurer IDE-en din som tidligere beskrevet, slik at du kan logge deg på databasen.

- bruk `-k test_navn` slik at kun den testen som feiler kjører
- da vil databasen ha alle data som de er ved utgang av testen
- i vscode, koble til databasen
- select all the things
- eventuelt gjør endringer i modellen og kjør `testenv dbt -- run -s modell_navn` for å se om det hjelper
