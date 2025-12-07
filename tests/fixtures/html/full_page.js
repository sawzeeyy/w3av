// Full HTML page with inline JavaScript
const page = `
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="/styles/main.css">
    <script src="/vendor.js"></script>
</head>
<body>
    <a href="/dashboard">Dashboard</a>
    <img src="logo.jpg" srcset="logo-sm.jpg 1x, logo-lg.jpg 2x">
    <form action="/api/submit">
        <button formaction="/api/preview">Preview</button>
    </form>
    <div data-url="https://cdn.example.com/data"></div>
    <script>
        const apiUrl = "/api/analytics";
        fetch("https://external.com/track");
        window.location.href = "/redirect";
    </script>
</body>
</html>
`;
