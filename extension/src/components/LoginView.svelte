<script lang="ts">
  import { authStore } from '../lib/auth-store.svelte';

  let email = $state('');
  let password = $state('');
  let isSignUp = $state(false);
  let errorMsg = $state('');
  let submitting = $state(false);

  async function handleGoogle() {
    submitting = true;
    errorMsg = '';
    const result = await authStore.signInWithGoogle();
    if (!result.success) {
      errorMsg = result.error || 'Google sign in failed';
    }
    submitting = false;
  }

  async function handleEmailSubmit() {
    if (!email || !password) {
      errorMsg = 'Please enter email and password';
      return;
    }
    submitting = true;
    errorMsg = '';

    const result = isSignUp
      ? await authStore.signUp(email, password)
      : await authStore.signInWithEmail(email, password);

    if (!result.success) {
      errorMsg = result.error || 'Authentication failed';
    }
    submitting = false;
  }
</script>

<div class="login-view">
  <div class="logo-section">
    <img src="/icon-128.png" alt="Ruh" class="logo" />
    <h1>Ruh</h1>
    <p class="tagline">Know what's in your products</p>
  </div>

  {#if errorMsg}
    <div class="error-banner">{errorMsg}</div>
  {/if}

  <button
    class="google-btn"
    onclick={handleGoogle}
    disabled={submitting}
  >
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
      <path d="M3.964 10.706A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.038l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.962L3.964 7.294C4.672 5.166 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
    Sign in with Google
  </button>

  <div class="divider">
    <span>or</span>
  </div>

  <form onsubmit={(e) => { e.preventDefault(); handleEmailSubmit(); }}>
    <input
      type="email"
      bind:value={email}
      placeholder="Email"
      class="input"
      disabled={submitting}
    />
    <input
      type="password"
      bind:value={password}
      placeholder="Password"
      class="input"
      disabled={submitting}
    />
    <button type="submit" class="email-btn" disabled={submitting}>
      {isSignUp ? 'Create Account' : 'Sign In'}
    </button>
  </form>

  <button
    class="toggle-btn"
    onclick={() => { isSignUp = !isSignUp; errorMsg = ''; }}
  >
    {isSignUp ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
  </button>
</div>

<style>
  .login-view {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 24px 24px;
    min-height: 100vh;
    background: var(--color-bg-primary, #fffbf5);
  }

  .logo-section {
    text-align: center;
    margin-bottom: 32px;
  }

  .logo {
    width: 64px;
    height: 64px;
    margin-bottom: 12px;
  }

  h1 {
    font-family: 'Cormorant Infant', serif;
    font-size: 32px;
    font-weight: 700;
    color: var(--color-text-primary, #3A3633);
    margin: 0 0 4px;
  }

  .tagline {
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    color: var(--color-text-secondary, #6B6560);
    margin: 0;
  }

  .error-banner {
    background: #fef2f2;
    color: #c53030;
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 13px;
    margin-bottom: 16px;
    width: 100%;
    max-width: 300px;
    text-align: center;
  }

  .google-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    width: 100%;
    max-width: 300px;
    padding: 12px 16px;
    background: white;
    border: 1px solid #e0d8cc;
    border-radius: 8px;
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    font-weight: 500;
    color: var(--color-text-primary, #3A3633);
    cursor: pointer;
    transition: all 150ms ease;
  }

  .google-btn:hover:not(:disabled) {
    background: #faf5ee;
    border-color: #c4baa8;
  }

  .google-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .divider {
    display: flex;
    align-items: center;
    width: 100%;
    max-width: 300px;
    margin: 20px 0;
    gap: 12px;
  }

  .divider::before,
  .divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #e0d8cc;
  }

  .divider span {
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    color: var(--color-text-secondary, #6B6560);
  }

  form {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
    max-width: 300px;
  }

  .input {
    padding: 10px 14px;
    border: 1px solid #e0d8cc;
    border-radius: 8px;
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    background: white;
    color: var(--color-text-primary, #3A3633);
    outline: none;
    transition: border-color 150ms ease;
  }

  .input:focus {
    border-color: var(--color-sage, #94A37C);
  }

  .email-btn {
    padding: 12px 16px;
    background: var(--color-sage, #94A37C);
    color: white;
    border: none;
    border-radius: 8px;
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 150ms ease;
  }

  .email-btn:hover:not(:disabled) {
    background: #7d8a68;
  }

  .email-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .toggle-btn {
    margin-top: 16px;
    background: none;
    border: none;
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    color: var(--color-sage, #94A37C);
    cursor: pointer;
    padding: 4px;
  }

  .toggle-btn:hover {
    text-decoration: underline;
  }
</style>
