<script>
    let message = "Loading...";

    async function fetchHello() {
        try {
            const res = await fetch("http://localhost:8000/api/hello");
            const data = await res.json();
            message = data.message;
        } catch (e) {
            message = "Failed to connect to backend";
        }
    }

    fetchHello();
</script>

<main>
    <h1>Hello from Svelte!</h1>
    <p>{message}</p>
</main>

<style>
    main {
        font-family: system-ui, sans-serif;
        padding: 2rem;
        text-align: center;
    }
</style>
