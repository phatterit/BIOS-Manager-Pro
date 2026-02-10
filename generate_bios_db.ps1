# generate_bios_db.ps1
# Wersja V4: Stabilna (Flat Logic + Safe Strings)

# Konfiguracja środowiska
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$JsonPath = "$PSScriptRoot\bios_versions.json"
$TempDir = "$env:TEMP\BiosCatalogs"

# Funkcja zapisu (UTF-8 bez BOM dla Pythona)
function Set-ContentTheRightWay {
    param($Path, $Content)
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

# Tworzenie folderu roboczego
if (-not (Test-Path $TempDir)) {
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
}

Write-Host "--- ROZPOCZYNAM POBIERANIE DANYCH (V4) ---" -ForegroundColor Cyan
$FinalHash = @{}

# ==========================================
# 1. DELL (Command Update Catalog)
# ==========================================
try {
    Write-Host "DELL -> Pobieranie pliku CAB..." -ForegroundColor Yellow
    $DellUrl = "https://downloads.dell.com/catalog/CatalogPC.cab"
    $DellCab = "$TempDir\DellCatalog.cab"
    
    Invoke-WebRequest $DellUrl -OutFile $DellCab -UseBasicParsing
    
    Write-Host "DELL -> Rozpakowywanie..." -ForegroundColor Yellow
    expand $DellCab -F:* $TempDir | Out-Null
    
    $DellXmlFile = Get-ChildItem "$TempDir\*.xml" | Sort-Object Length -Descending | Select-Object -First 1
    
    if ($DellXmlFile) {
        Write-Host "DELL -> Analiza XML..." -ForegroundColor Yellow
        [xml]$xml = Get-Content $DellXmlFile.FullName
        
        $counter = 0
        $Components = $xml.GetElementsByTagName("SoftwareComponent")
        
        foreach ($comp in $Components) {
            # Pomijamy nie-BIOSy
            if ($comp.ComponentType -ne "BIOS") { continue }
            if (-not $comp.dellVersion) { continue }
            
            # Bezpieczna nawigacja po XML
            if ($comp.SupportedSystems -and $comp.SupportedSystems.Brand) {
                foreach ($brand in $comp.SupportedSystems.Brand) {
                    if ($brand.Model) {
                        foreach ($model in $brand.Model) {
                            $mName = $model.Name
                            if ($mName) {
                                $cleanName = "Dell " + $mName.Trim()
                                $FinalHash[$cleanName] = $comp.dellVersion
                                $counter++
                            }
                        }
                    }
                }
            }
        }
        Write-Host "DELL -> Sukces. Znaleziono modeli: $counter" -ForegroundColor Green
    }
} catch {
    Write-Host "DELL -> BLAD: $_" -ForegroundColor Red
}

# ==========================================
# 2. LENOVO (XML Text Parsing)
# ==========================================
try {
    Write-Host "LENOVO -> Pobieranie XML..." -ForegroundColor Yellow
    $LenovoUrl = "https://download.lenovo.com/cdrt/td/catalog.xml"
    
    $rawString = (Invoke-WebRequest $LenovoUrl -UseBasicParsing).Content
    
    # Odcinamy podpis cyfrowy (bezpieczna metoda tekstowa)
    $endTag = "</catalog>"
    $endIndex = $rawString.LastIndexOf($endTag)
    
    if ($endIndex -gt 0) {
        $cleanXmlString = $rawString.Substring(0, $endIndex + $endTag.Length)
        [xml]$lxml = $cleanXmlString
        
        $lCounter = 0
        if ($lxml.catalog -and $lxml.catalog.item) {
            foreach ($item in $lxml.catalog.item) {
                if ($item.type -eq "BIOS") {
                    $modelName = "Lenovo " + $item.model
                    $version = $item.version
                    $FinalHash[$modelName] = $version
                    $lCounter++
                }
            }
        }
        Write-Host "LENOVO -> Sukces. Znaleziono modeli: $lCounter" -ForegroundColor Green
    } else {
        Write-Host "LENOVO -> Nie udalo sie wyczyscic XML." -ForegroundColor Red
    }
} catch {
    Write-Host "LENOVO -> BLAD: $_" -ForegroundColor Red
}

# ==========================================
# 3. ZAPIS
# ==========================================
$total = $FinalHash.Count
Write-Host "--- PODSUMOWANIE ---" -ForegroundColor Cyan
Write-Host "Lacznie modeli: $total" -ForegroundColor Cyan

if ($total -gt 0) {
    $JsonContent = $FinalHash | ConvertTo-Json -Depth 2
    Set-ContentTheRightWay -Path $JsonPath -Content $JsonContent
    Write-Host "Baza zapisana w: $JsonPath" -ForegroundColor Green
} else {
    Write-Host "OSTRZEZENIE: Baza jest pusta." -ForegroundColor Red
}