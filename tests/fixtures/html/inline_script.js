// HTML with inline script
const html = `
<script>
    const api = "/api/data";
    fetch("https://analytics.com/track");
    window.location = "/redirect";
</script>
`;
