using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Shop.Api.Authorization;
using Shop.Application.Common;
using Shop.Application.Invoices;
using Shop.Domain.Invoices;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/invoices")]
[Authorize]
public sealed class InvoicesController(ISender mediator, IAuthorizationService authorization) : ControllerBase
{
    /// <summary>Lists invoices for finance staff, optionally filtered by status.</summary>
    [HttpGet]
    [Authorize(Policy = Policies.Finance)]
    public async Task<ActionResult<PagedResult<InvoiceDto>>> List(
        [FromQuery] InvoiceStatus? status, [FromQuery] int? page, [FromQuery] int? pageSize, CancellationToken cancellationToken) =>
        Ok(await mediator.Send(new ListInvoicesQuery(status, page, pageSize), cancellationToken));

    /// <summary>Retrives a single invoice. Only the owning customer or finance staff may read it.</summary>
    [HttpGet("{id:guid}")]
    public async Task<ActionResult<InvoiceDto>> GetById(Guid id, CancellationToken cancellationToken)
    {
        var invoice = await mediator.Send(new GetInvoiceQuery(id), cancellationToken);
        if (!await IsOwnerAsync(invoice))
        {
            return Forbid();
        }

        return Ok(invoice);
    }

    /// <summary>Returns the payments booked against an invoice.</summary>
    [HttpGet("{id:guid}/payments")]
    public async Task<ActionResult<IReadOnlyList<PaymentDto>>> GetPayments(Guid id, CancellationToken cancellationToken)
    {
        var invoice = await mediator.Send(new GetInvoiceQuery(id), cancellationToken);
        if (!await IsOwnerAsync(invoice))
        {
            return Forbid();
        }

        return Ok(await mediator.Send(new GetInvoicePaymentsQuery(id), cancellationToken));
    }

    /// <summary>Creates and issues an invoice for an order.</summary>
    [HttpPost]
    [Authorize(Policy = Policies.Finance)]
    public async Task<ActionResult<InvoiceDto>> Create(CreateInvoiceCommand command, CancellationToken cancellationToken)
    {
        var invoice = await mediator.Send(command, cancellationToken);
        return CreatedAtAction(nameof(GetById), new { id = invoice.Id }, invoice);
    }

    /// <summary>Charges the outstanding amount with the customer's stored payment method.</summary>
    [HttpPost("{id:guid}/pay")]
    public async Task<ActionResult<PaymentDto>> Pay(Guid id, PayInvoiceRequest request, CancellationToken cancellationToken)
    {
        var invoice = await mediator.Send(new GetInvoiceQuery(id), cancellationToken);
        if (!await IsOwnerAsync(invoice))
        {
            return Forbid();
        }

        return Ok(await mediator.Send(new PayInvoiceCommand(id, request.PaymentMethodToken), cancellationToken));
    }

    private async Task<bool> IsOwnerAsync(InvoiceDto invoice) =>
        (await authorization.AuthorizeAsync(User, invoice, Policies.InvoiceOwner)).Succeeded;
}
