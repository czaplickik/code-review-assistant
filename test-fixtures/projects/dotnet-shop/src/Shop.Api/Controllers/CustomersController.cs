using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Shop.Api.Authorization;
using Shop.Application.Common;
using Shop.Application.Customers;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/customers")]
[Authorize(Policy = Policies.Staff)]
public sealed class CustomersController(ICustomerService customers) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<PagedResult<CustomerDto>>> List([FromQuery] string? search, [FromQuery] int? page, [FromQuery] int? pageSize, CancellationToken cancellationToken)
    {
        return Ok(await customers.ListAsync(search, page, pageSize, cancellationToken));
    }

    [HttpGet("{id:guid}")]
    public async Task<ActionResult<CustomerDto>> Get(Guid id, CancellationToken cancellationToken)
        => Ok(await customers.GetAsync(id, cancellationToken));
    [HttpPost]
    public async Task<ActionResult<CustomerDto>> Create(CreateCustomerRequest request, CancellationToken cancellationToken)
    {
        var customer = await customers.CreateAsync(request, cancellationToken);
        return CreatedAtAction(nameof(Get), new { id = customer.Id }, customer);
    }

    [HttpPut("{id:guid}")]
    public async Task<ActionResult<CustomerDto>> Update(Guid id, UpdateCustomerRequest request, CancellationToken cancellationToken) => Ok(await customers.UpdateAsync(id, request, cancellationToken));
}
