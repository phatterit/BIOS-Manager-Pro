# BIOS-Manager-Pro
Narzędzie SecOps oparte na Flask i Pandas do automatycznej analizy zgodności wersji BIOS w infrastrukturze IT. Oferuje import danych z CSV/XLSX, ocenę ryzyka, wizualizację statystyk (Heatmap) oraz panel administracyjny z obsługą bazy JSON/SQL.

# 🛡️ BIOS Manager Pro

**Zaawansowany Dashboard SecOps do analizy i monitorowania wersji BIOS w środowisku korporacyjnym.**

Aplikacja rozwiązuje problem ręcznego weryfikowania wersji oprogramowania układowego (BIOS/UEFI) na setkach komputerów. Pozwala na wgranie raportu z inwentaryzacji (Excel/CSV), automatycznie porównuje wersje z wewnętrzną bazą wiedzy i generuje raport bezpieczeństwa z oceną ryzyka.

![BIOS Manager Screenshot]


## 🚀 Główne Funkcjonalności

### 1. Skaner i Analiza
* **Import Danych:** Obsługa plików `.xlsx` oraz `.csv` (np. z SCCM, Lansweeper, OCS Inventory).
* **Inteligentne Parsowanie:** Algorytmy Regex (`packaging.version`) radzące sobie z różnymi formatami wersji (np. "1.20", "A14", "Ver 1.0 (A03)").
* **Risk Score:** Automatyczne obliczanie poziomu zagrożenia organizacji (od "Bunkier" do "Krytyczny").

### 2. Wizualizacja Danych (Cyberpunk UI)
* **Heatmapa Oddziałów:** Wizualna reprezentacja zgodności w poszczególnych lokalizacjach firmy.
* **Wykresy:** Status aktualizacji (OK / Outdated / Unknown).
* **Ranking:** Lista oddziałów posortowana od najmniej bezpiecznych.
* **Nowoczesny Design:** Ciemny motyw z neonowymi akcentami (Bootstrap 5 + Custom CSS).

### 3. Panel Administratora
* **Baza Wiedzy:** Zarządzanie wzorcami wersji BIOS (SQLAlchemy + SQLite).
* **Import/Eksport:** Możliwość szybkiego zasilenia bazy plikiem JSON (`import_json_db`).
* **Edycja:** Oznaczanie modeli jako "OLD" (brak wsparcia producenta).

## 🛠️ Technologie

* **Backend:** Python 3.10+, Flask
* **Baza Danych:** SQLite + SQLAlchemy
* **Analiza Danych:** Pandas, OpenPyXL
* **Frontend:** HTML5, Jinja2, Bootstrap 5, Chart.js
* **Style:** Custom CSS (Neon/Dark Mode)


