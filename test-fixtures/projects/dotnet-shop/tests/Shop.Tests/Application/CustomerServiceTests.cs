using FluentValidation;
using Shop.Application.Abstractions;
using Shop.Application.Common;
using Shop.Application.Customers;
using Shop.Domain.Customers;
using Shop.Domain.Exceptions;

namespace Shop.Tests.Application;

public sealed class CustomerServiceTests
{
    private readonly Mock<ICustomerRepository> _customers = new();
    private readonly Mock<IUnitOfWork> _unitOfWork = new();
    private readonly CustomerService _service;

    public CustomerServiceTests()
    {
        _service = new CustomerService(
            _customers.Object,
            _unitOfWork.Object,
            new CreateCustomerRequestValidator(),
            new UpdateCustomerRequestValidator(),
            TimeProvider.System);
    }

    [Fact]
    public async Task CreateAsync_ValidRequest_StoresLowerCaseEmailAndSaves()
    {
        var result = await _service.CreateAsync(new CreateCustomerRequest("Ada Lovelace", " Ada@Example.com "), CancellationToken.None);

        result.Email.Should().Be("ada@example.com");
        _customers.Verify(r => r.Add(It.Is<Customer>(c => c.Email == "ada@example.com")), Times.Once);
        _unitOfWork.Verify(u => u.SaveChangesAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task CreateAsync_DuplicateEmail_ThrowsDuplicateCustomer()
    {
        _customers.Setup(r => r.EmailExistsAsync("ada@example.com", It.IsAny<CancellationToken>())).ReturnsAsync(true);

        var act = () => _service.CreateAsync(new CreateCustomerRequest("Ada", "ada@example.com"), CancellationToken.None);

        await act.Should().ThrowAsync<DuplicateCustomerException>();
        _unitOfWork.Verify(u => u.SaveChangesAsync(It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task CreateAsync_InvalidEmail_ThrowsValidationException()
    {
        var act = () => _service.CreateAsync(new CreateCustomerRequest("Ada", "not-an-email"), CancellationToken.None);

        await act.Should().ThrowAsync<ValidationException>();
    }

    [Fact]
    public async Task GetAsync_UnknownId_ThrowsNotFound()
    {
        var act = () => _service.GetAsync(Guid.NewGuid(), CancellationToken.None);

        await act.Should().ThrowAsync<NotFoundException>();
    }

    [Fact]
    public async Task ListAsync_PageSizeAboveMax_ClampsToMaxPageSize()
    {
        _customers
            .Setup(r => r.ListAsync(null, 0, Paging.MaxPageSize, It.IsAny<CancellationToken>()))
            .ReturnsAsync(([], 0));

        var result = await _service.ListAsync(null, 1, 10_000, CancellationToken.None);

        result.PageSize.Should().Be(Paging.MaxPageSize);
    }
}
