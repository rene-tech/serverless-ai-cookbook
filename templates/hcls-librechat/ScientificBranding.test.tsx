import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import Footer from './Footer';
import AuthFooter from '../Auth/Footer';

jest.mock('~/data-provider', () => ({ useGetStartupConfig: () => ({ data: undefined }) }));
jest.mock('~/hooks', () => ({ useLocalize: () => (key: string) => key }));

test('default chat footer contains both actual brand elements', () => {
  render(<Footer startupConfig={null} />);
  expect(screen.getByText('Powered by')).toBeInTheDocument();
  expect(screen.getByRole('img', { name: 'NVIDIA' }).tagName.toLowerCase()).toBe('svg');
  expect(screen.getByRole('img', { name: 'Nebius' })).toHaveAttribute('src', '/assets/nebius-logo.svg');
});

test('login and registration retain partner branding before configuration loads', () => {
  render(<AuthFooter startupConfig={undefined} />);
  expect(screen.getByRole('img', { name: 'Nebius' })).toBeInTheDocument();
  expect(screen.getByRole('img', { name: 'NVIDIA' })).toBeInTheDocument();
});

test('policy links remain available with both partner logos', () => {
  render(<Footer startupConfig={{ interface: {
    privacyPolicy: { externalUrl: 'https://example.com/privacy' },
    termsOfService: { externalUrl: 'https://example.com/terms' },
  } }} />);
  expect(screen.getByRole('img', { name: 'Nebius' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'com_ui_privacy_policy' })).toHaveAttribute('href', 'https://example.com/privacy');
  expect(screen.getByRole('link', { name: 'com_ui_terms_of_service' })).toHaveAttribute('href', 'https://example.com/terms');
});
