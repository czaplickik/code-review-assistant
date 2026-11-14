using Microsoft.AspNetCore.Authorization;
using Shop.Application.Invoices;

namespace Shop.Api.Authorization;

public static class Policies
{
    /// <summary>Resource-based: the caller owns the invoice (customer_id claim) or is finance staff.</summary>
    public const string InvoiceOwner = "InvoiceOwner";
    public const string Finance = "Finance";
    public const string Staff = "Staff";
}

public static class Roles
{
    public const string Finance = "finance";
    public const string Support = "support";
}

public sealed class InvoiceOwnerRequirement : IAuthorizationRequirement;

/// <summary>
/// Grants <see cref="Policies.InvoiceOwner"/> when the authenticated customer owns the invoice.
/// Finance staff may access every invoice. Use with
/// <c>IAuthorizationService.AuthorizeAsync(User, invoiceDto, Policies.InvoiceOwner)</c>.
/// </summary>
public sealed class InvoiceOwnerAuthorizationHandler : AuthorizationHandler<InvoiceOwnerRequirement, InvoiceDto>
{
    public const string CustomerIdClaim = "customer_id";

    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context, InvoiceOwnerRequirement requirement, InvoiceDto resource)
    {
        if (context.User.IsInRole(Roles.Finance))
        {
            context.Succeed(requirement);
            return Task.CompletedTask;
        }

        var claim = context.User.FindFirst(CustomerIdClaim)?.Value;
        if (Guid.TryParse(claim, out var customerId) && customerId == resource.CustomerId)
        {
            context.Succeed(requirement);
        }

        return Task.CompletedTask;
    }
}
