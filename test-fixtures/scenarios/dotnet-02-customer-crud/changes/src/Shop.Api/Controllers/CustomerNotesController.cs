using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Shop.Api.Authorization;
using Shop.Application.Common;
using Shop.Application.Customers;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/customers/{customerId:guid}/notes")]
[Authorize(Policy = Policies.Staff)]
public sealed class CustomerNotesController(ICustomerNoteService notes) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<PagedResult<CustomerNoteDto>>> List(
        Guid customerId, [FromQuery] int? page, [FromQuery] int? pageSize, CancellationToken cancellationToken) =>
        Ok(await notes.ListAsync(customerId, page, pageSize, cancellationToken));

    [HttpGet("{noteId:guid}")]
    public async Task<ActionResult<CustomerNoteDto>> Get(Guid customerId, Guid noteId, CancellationToken cancellationToken) =>
        Ok(await notes.GetAsync(customerId, noteId, cancellationToken));

    [HttpPost]
    public async Task<ActionResult<CustomerNoteDto>> Create(
        Guid customerId, CreateCustomerNoteRequest request, CancellationToken cancellationToken)
    {
        var note = await notes.CreateAsync(customerId, AuthorId(), request, cancellationToken);
        return CreatedAtAction(nameof(Get), new { customerId, noteId = note.Id }, note);
    }

    [HttpPut("{noteId:guid}")]
    public async Task<ActionResult<CustomerNoteDto>> Update(
        Guid customerId, Guid noteId, UpdateCustomerNoteRequest request, CancellationToken cancellationToken) =>
        Ok(await notes.UpdateAsync(customerId, noteId, request, cancellationToken));

    [HttpDelete("{noteId:guid}")]
    public async Task<IActionResult> Delete(Guid customerId, Guid noteId, CancellationToken cancellationToken)
    {
        await notes.DeleteAsync(customerId, noteId, cancellationToken);
        return NoContent();
    }

    private string AuthorId() =>
        User.FindFirstValue("sub") ?? throw new InvalidOperationException("Authenticated user has no 'sub' claim.");
}
