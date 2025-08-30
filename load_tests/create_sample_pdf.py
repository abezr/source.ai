from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def create_sample_pdf(filename):
    c = canvas.Canvas(filename, pagesize=letter)
    c.drawString(100, 750, "Sample PDF for Load Testing")
    c.drawString(100, 730, "This is a test document.")
    c.drawString(100, 710, "It contains some sample text.")
    c.save()


if __name__ == "__main__":
    create_sample_pdf("load_tests/sample.pdf")
