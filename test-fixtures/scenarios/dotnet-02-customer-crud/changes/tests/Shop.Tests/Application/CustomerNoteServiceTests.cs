using FluentValidation;
using Shop.Application.Abstractions;
using Shop.Application.Common;
using Shop.Application.Customers;
using Shop.Domain.Customers;
using Shop.Domain.Exceptions;

namespace Shop.Tests.Application;

public sealed class CustomerNoteServiceTests
{
    private static readonly Guid CustomerId = Guid.NewGuid();

    private readonly Mock<ICustomerRepository> _customers = new();
    private readonly Mock<ICustomerNoteRepository> _notes = new();
    private readonly Mock<IUnitOfWork> _unitOfWork = new();
    private readonly CustomerNoteService _service;

    public CustomerNoteServiceTests()
    {
        _customers.Setup(r => r.ExistsAsync(CustomerId, It.IsAny<CancellationToken>())).ReturnsAsync(true);

        _service = new CustomerNoteService(
            _customers.Object,
            _notes.Object,
            _unitOfWork.Object,
            new CreateCustomerNoteRequestValidator(),
            new UpdateCustomerNoteRequestValidator(),
            TimeProvider.System);
    }

    [Fact]
    public async Task CreateAsync_ValidRequest_AddsNoteWithAuthorAndSaves()
    {
        var result = await _service.CreateAsync(
            CustomerId, "staff-42", new CreateCustomerNoteRequest("  Agreed payment plan until March  ", true), CancellationToken.None);

        result.Body.Should().Be("Agreed payment plan until March");
        result.AuthorId.Should().Be("staff-42");
        result.IsPinned.Should().BeTrue();
        _notes.Verify(r => r.Add(It.Is<CustomerNote>(n => n.CustomerId == CustomerId)), Times.Once);
        _unitOfWork.Verify(u => u.SaveChangesAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task CreateAsync_UnknownCustomer_ThrowsNotFound()
    {
        var act = () => _service.CreateAsync(
            Guid.NewGuid(), "staff-42", new CreateCustomerNoteRequest("Note", false), CancellationToken.None);

        await act.Should().ThrowAsync<NotFoundException>();
        _notes.Verify(r => r.Add(It.IsAny<CustomerNote>()), Times.Never);
    }

    [Fact]
    public async Task CreateAsync_EmptyBody_ThrowsValidationException()
    {
        var act = () => _service.CreateAsync(
            CustomerId, "staff-42", new CreateCustomerNoteRequest("", false), CancellationToken.None);

        await act.Should().ThrowAsync<ValidationException>();
    }

    [Fact]
    public async Task UpdateAsync_NoteOfAnotherCustomer_ThrowsNotFound()
    {
        _notes
            .Setup(r => r.GetAsync(CustomerId, It.IsAny<Guid>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync((CustomerNote?)null);

        var act = () => _service.UpdateAsync(
            CustomerId, Guid.NewGuid(), new UpdateCustomerNoteRequest("Changed", false), CancellationToken.None);

        await act.Should().ThrowAsync<NotFoundException>();
        _unitOfWork.Verify(u => u.SaveChangesAsync(It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task UpdateAsync_ExistingNote_EditsBodyAndSetsUpdatedAt()
    {
        var note = CustomerNote.Create(CustomerId, "Original", "staff-1", false, DateTimeOffset.UtcNow.AddDays(-1));
        _notes.Setup(r => r.GetAsync(CustomerId, note.Id, It.IsAny<CancellationToken>())).ReturnsAsync(note);

        var result = await _service.UpdateAsync(
            CustomerId, note.Id, new UpdateCustomerNoteRequest("Changed", true), CancellationToken.None);

        result.Body.Should().Be("Changed");
        result.IsPinned.Should().BeTrue();
        result.UpdatedAt.Should().NotBeNull();
    }

    [Fact]
    public async Task DeleteAsync_ExistingNote_RemovesAndSaves()
    {
        var note = CustomerNote.Create(CustomerId, "Obsolete", "staff-1", false, DateTimeOffset.UtcNow);
        _notes.Setup(r => r.GetAsync(CustomerId, note.Id, It.IsAny<CancellationToken>())).ReturnsAsync(note);

        await _service.DeleteAsync(CustomerId, note.Id, CancellationToken.None);

        _notes.Verify(r => r.Remove(note), Times.Once);
        _unitOfWork.Verify(u => u.SaveChangesAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task ListAsync_PageSizeAboveMax_ClampsToMaxPageSize()
    {
        _notes
            .Setup(r => r.ListAsync(CustomerId, 0, Paging.MaxPageSize, It.IsAny<CancellationToken>()))
            .ReturnsAsync(([], 0));

        var result = await _service.ListAsync(CustomerId, 1, 500, CancellationToken.None);

        result.PageSize.Should().Be(Paging.MaxPageSize);
        result.Items.Should().BeEmpty();
    }
}
