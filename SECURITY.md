# Security Policy

## Supported versions

Security fixes are provided for the latest released version and the current `main` branch. Older releases may not receive security updates; upgrade before reporting a vulnerability when possible.

## Data handled by the extension

BridgeCF's extension reads the configured Codeforces handle and information from the current problem page DOM needed to identify the problem and ground a hint (including the problem statement). It does not request or collect Codeforces passwords, cookies, or private submission contents. The backend may retrieve public Codeforces submission history for the configured handle to estimate solved-problem mastery.

The extension sends the handle, current problem ID, and available problem statement to the configured BridgeCF API base URL. Users can inspect or change that URL in the extension's advanced settings.

## Reporting a vulnerability

Please report security issues privately through [GitHub Security Advisories](https://github.com/Krishna27Singh/BridgeCF/security/advisories/new). If private vulnerability reporting is unavailable, contact the repository owner through the private contact method listed on the [GitHub profile](https://github.com/Krishna27Singh). Do not open a public issue with exploit details.

Include the affected version or commit, impact, and concise reproduction steps. Please allow maintainers time to investigate and coordinate a fix before public disclosure.
