using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Shop.Api.Authorization;
using Shop.Application.Invoices;

namespace Shop.Tests.Api;

public sealed class InvoiceOwnerAuthorizationHandlerTests
{
    private readonly InvoiceOwnerAuthorizationHandler _handler = new();

    [Fact]
    public async Task HandleAsync_CustomerOwnsInvoice_Succeeds()
    {
        var customerId = Guid.NewGuid();
        var context = Context(User(new Claim("customer_id", customerId.ToString())), Invoice(customerId));

        await _handler.HandleAsync(context);

        context.HasSucceeded.Should().BeTrue();
    }

    [Fact]
    public async Task HandleAsync_OtherCustomersInvoice_DoesNotSucceed()
    {
        var context = Context(User(new Claim("customer_id", Guid.NewGuid().ToString())), Invoice(Guid.NewGuid()));

        await _handler.HandleAsync(context);

        context.HasSucceeded.Should().BeFalse();
    }

    [Fact]
    public async Task HandleAsync_FinanceRole_SucceedsForAnyInvoice()
    {
        var context = Context(User(new Claim("roles", Roles.Finance)), Invoice(Guid.NewGuid()));

        await _handler.HandleAsync(context);

        context.HasSucceeded.Should().BeTrue();
    }

    [Fact]
    public async Task HandleAsync_MissingCustomerClaim_DoesNotSucceed()
    {
        var context = Context(User(), Invoice(Guid.NewGuid()));

        await _handler.HandleAsync(context);

        context.HasSucceeded.Should().BeFalse();
    }

    private static AuthorizationHandlerContext Context(ClaimsPrincipal user, InvoiceDto invoice) =>
        new([new InvoiceOwnerRequirement()], user, invoice);

    private static ClaimsPrincipal User(params Claim[] claims) =>
        new(new ClaimsIdentity(claims, authenticationType: "Bearer", nameType: "sub", roleType: "roles"));

    private static InvoiceDto Invoice(Guid customerId) => new(
        Guid.NewGuid(), "INV-2026-000300", customerId, null, "Issued", "EUR", 10m, 0m, 10m,
        new DateOnly(2026, 12, 1), DateTimeOffset.UtcNow, null, []);
}
