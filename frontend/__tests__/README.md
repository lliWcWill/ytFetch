# ytFetch Frontend Auth Flow Tests

This directory contains comprehensive unit and integration tests for the authentication flows in ytFetch.

## Test Coverage

### 1. **AuthProvider Tests** (`providers/__tests__/AuthProvider.test.tsx`)
- Initial state and loading behavior
- Auth state changes (sign in, sign out, token refresh)
- Auth methods (Google sign in, sign out, error handling)
- Session refresh and persistence
- Error boundary testing

### 2. **Auth Callback Route Tests** (`app/auth/callback/__tests__/route.test.ts`)
- Successful authentication flow
- Redirect preservation through auth
- Open redirect protection
- Error handling (OAuth errors, code exchange errors)
- Query parameter handling

### 3. **Header Component Tests** (`components/__tests__/Header.test.tsx`)
- Authenticated vs unauthenticated UI states
- Auth state change event handling
- User menu interactions
- Mobile menu behavior
- Navigation link highlighting

### 4. **Pricing Auth Flow Tests** (`app/pricing/__tests__/pricing-auth-flow.test.tsx`)
- Package selection preservation through auth
- Auto-checkout after authentication
- Direct checkout for authenticated users
- Query parameter cleanup
- Error handling

### 5. **Auth Middleware Tests** (`middleware/__tests__/auth.test.ts`)
- Protected route access control
- Auth route redirects for authenticated users
- Public route access
- Redirect parameter preservation
- Edge case handling

### 6. **Integration Tests** (`__tests__/integration/auth-flow.test.tsx`)
- End-to-end auth flow
- Concurrent auth operations
- Auth persistence
- Error recovery

### 7. **AuthSuccessHandler Tests** (`components/__tests__/AuthSuccessHandler.test.tsx`)
- Auth success parameter cleanup
- Auto-checkout flow with different packages
- Error handling (API, Stripe, network errors)
- URL parameter preservation

## Running the Tests

### Install Dependencies
```bash
cd frontend
npm install
```

### Run All Tests
```bash
npm test
```

### Run Tests in Watch Mode
```bash
npm run test:watch
```

### Run Tests with Coverage
```bash
npm run test:coverage
```

### Run Specific Test File
```bash
npm test -- AuthProvider.test.tsx
```

### Run Tests Matching Pattern
```bash
npm test -- --testNamePattern="auth flow"
```

## Test Utilities

The `__tests__/utils/auth-test-utils.tsx` file provides helpful utilities:

- `createMockUser()` - Create mock Supabase user objects
- `createMockSession()` - Create mock Supabase session objects
- `renderWithAuth()` - Render components with AuthProvider wrapper
- `AuthStateMocker` - Simulate auth state changes
- `OAuthFlowMocker` - Mock OAuth redirect flows

## Writing New Auth Tests

When adding new auth-related features:

1. **Unit Tests**: Test individual components/functions in isolation
2. **Integration Tests**: Test how components work together
3. **Edge Cases**: Test error conditions and unusual flows
4. **Security**: Test redirect validation and token handling

Example test structure:
```typescript
describe('Feature Name', () => {
  beforeEach(() => {
    // Setup mocks
  })

  describe('Happy Path', () => {
    it('should handle normal flow', async () => {
      // Test implementation
    })
  })

  describe('Error Handling', () => {
    it('should handle errors gracefully', async () => {
      // Test error scenarios
    })
  })
})
```

## Common Testing Patterns

### Mocking Supabase Auth
```typescript
const mockSupabaseClient = {
  auth: {
    signInWithOAuth: jest.fn(),
    signOut: jest.fn(),
    getSession: jest.fn(),
  }
}
```

### Testing Auth State Changes
```typescript
act(() => {
  authStateChangeCallback('SIGNED_IN', mockSession)
})

await waitFor(() => {
  expect(screen.getByText('Logged in')).toBeInTheDocument()
})
```

### Testing Protected Routes
```typescript
const request = new NextRequest('/protected-route')
const response = await authMiddleware(request)
expect(response.headers.get('location')).toBe('/login')
```

## Debugging Tests

- Use `screen.debug()` to see the current DOM
- Add `console.log` statements in test code
- Use `--verbose` flag for detailed test output
- Check `coverage/lcov-report/index.html` for coverage gaps

## CI/CD Integration

These tests should run in your CI pipeline:
```yaml
- name: Run Frontend Tests
  run: |
    cd frontend
    npm ci
    npm test -- --coverage --watchAll=false
```