"""dotnet-01-trivial: typo fixes, a private rename, a corrected test expectation, a script fix.

Applied to the working tree after the base commit, so every edit shows up as an uncommitted
modification. Each replacement must match exactly the expected number of times.
"""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])

EDITS = {
    # log message typo
    "src/Shop.Infrastructure/Payments/PaymentGatewayClient.cs": [
        ("Paymnet gateway returned", "Payment gateway returned", 1),
    ],
    # XML doc typos on a high fan-in type (comment-only change)
    "src/Shop.Domain/Common/Money.cs": [
        ("Immutable monetery amount", "Immutable monetary amount", 1),
        ("remainder cents are distribued", "remainder cents are distributed", 1),
    ],
    # XML doc typo
    "src/Shop.Api/Controllers/InvoicesController.cs": [
        ("Retrives a single invoice", "Retrieves a single invoice", 1),
    ],
    # comment typos
    "src/Shop.Infrastructure/BackgroundJobs/OverdueInvoiceNotifier.cs": [
        ("an invoice recieves a payment", "an invoice receives a payment", 1),
        ("concurency conflict", "concurrency conflict", 1),
    ],
    # wrong expected value: 2 x 19.99 + 5.01 = 44.99 (the test was failing)
    "tests/Shop.Tests/Domain/InvoiceTests.cs": [
        ("invoice.Total.Should().Be(Money.Of(45.99m, \"EUR\"));", "invoice.Total.Should().Be(Money.Of(44.99m, \"EUR\"));", 1),
    ],
    # wrong project path (typo) and drop ignoring -Connection
    "scripts/reset-db.ps1": [
        ("src/Shop.Infrastucture", "src/Shop.Infrastructure", 2),
        ("dotnet ef database drop --force --project src/Shop.Infrastructure --startup-project src/Shop.Api\n",
         "dotnet ef database drop --force --project src/Shop.Infrastructure --startup-project src/Shop.Api --connection $Connection\n", 1),
    ],
    # private helper rename
    "src/Shop.Application/Customers/CustomerService.cs": [
        ("Normalise(", "NormalizeEmail(", 2),
    ],
}

# word-boundary renames (private method + locals) in the notifier
REGEX_EDITS = {
    "src/Shop.Infrastructure/BackgroundJobs/OverdueInvoiceNotifier.cs": [
        (r"\bCreateEvt\b", "CreateOverdueEvent", 2),
        (r"\binv\b", "invoice", 10),
        (r"\bdue\b(?=\s*=|\.Count|\))", "overdueInvoices", 4),
    ],
}

for rel, edits in EDITS.items():
    path = root / rel
    text = path.read_text(encoding="utf-8")
    for old, new, count in edits:
        found = text.count(old)
        if found != count:
            sys.exit(f"{rel}: expected {count}x {old!r}, found {found}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")

for rel, edits in REGEX_EDITS.items():
    path = root / rel
    text = path.read_text(encoding="utf-8")
    for pattern, new, count in edits:
        text, n = re.subn(pattern, new, text)
        if n != count:
            sys.exit(f"{rel}: expected {count}x /{pattern}/, replaced {n}")
    path.write_text(text, encoding="utf-8")
