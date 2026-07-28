<script>
  let email = "";
  let productUpdates = false;
  let serviceNotices = true;
</script>

<svelte:head>
  <title>Notification preferences</title>
</svelte:head>

<main class="settings-shell">
  <p class="eyebrow">Account settings</p>
  <h1>Notification preferences</h1>
  <p>Choose which messages this local demonstration should remember.</p>

  <form class="preference-form">
    <label>
      <span>Email address</span>
      <input bind:value={email} name="email" type="email" />
    </label>

    <fieldset>
      <legend>Messages</legend>
      <label><input bind:checked={productUpdates} type="checkbox" /> Product updates</label>
      <label><input bind:checked={serviceNotices} type="checkbox" /> Service notices</label>
    </fieldset>

    <button>Save preferences</button>
  </form>
</main>
