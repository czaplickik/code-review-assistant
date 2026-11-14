using Shop.Application.Customers;

namespace Shop.Tests.Application;

public sealed class CustomerNoteValidatorTests
{
    private readonly CreateCustomerNoteRequestValidator _createValidator = new();
    private readonly UpdateCustomerNoteRequestValidator _updateValidator = new();

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void Validate_BlankBody_IsInvalid(string body)
    {
        _createValidator.Validate(new CreateCustomerNoteRequest(body, false)).IsValid.Should().BeFalse();
        _updateValidator.Validate(new UpdateCustomerNoteRequest(body, false)).IsValid.Should().BeFalse();
    }

    [Fact]
    public void Validate_ShortBody_IsValid()
    {
        _createValidator.Validate(new CreateCustomerNoteRequest("Prefers invoices in English", false)).IsValid.Should().BeTrue();
    }

    [Fact]
    public void Validate_BodyLongerThanLimit_IsInvalid()
    {
        var body = new string('x', 4001);

        _createValidator.Validate(new CreateCustomerNoteRequest(body, false)).IsValid.Should().BeFalse();
    }
}
