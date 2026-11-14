using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Shop.Api.Authorization;
using Shop.Domain.Payments;
using Shop.Infrastructure.Persistence;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/reconciliation")]
[Authorize(Policy = Policies.Finance)]
public sealed class ReconciliationController(ShopDbContext db) : ControllerBase
{
    /// <summary>Bank transactions that could not be matched automatically, newest first.</summary>
    [HttpGet("unmatched")]
    public async Task<ActionResult<List<BankTransaction>>> GetUnmatched(CancellationToken cancellationToken)
    {
        var transactions = await db.Set<BankTransaction>()
            .Where(t => t.Status == BankTransactionStatus.Unmatched)
            .OrderByDescending(t => t.BookedAt)
            .ToListAsync(cancellationToken);

        return Ok(transactions);
    }
}
