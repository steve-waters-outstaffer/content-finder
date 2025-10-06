import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ContentFinder from '../ContentFinder';

const createResponse = (data: unknown, init?: ResponseInit) =>
    new Response(JSON.stringify(data), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
        ...init,
    });

describe('ContentFinder', () => {
    const originalFetch = global.fetch;

    beforeEach(() => {
        vi.restoreAllMocks();
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    it('renders structured article analysis when Gemini returns valid JSON', async () => {
        const fetchMock = vi.fn((input: RequestInfo | URL) => {
            const url = typeof input === 'string' ? input : input.toString();
            if (url.endsWith('/search')) {
                return Promise.resolve(
                    createResponse({
                        results: [
                            {
                                url: 'https://example.com/article-1',
                                title: 'Example Article',
                                description: 'An example description',
                            },
                        ],
                    }),
                );
            }
            if (url.endsWith('/scrape')) {
                return Promise.resolve(
                    createResponse({
                        results: [
                            {
                                url: 'https://example.com/article-1',
                                title: 'Example Article',
                                markdown: '# Heading\n\nContent',
                                success: true,
                            },
                        ],
                    }),
                );
            }
            if (url.endsWith('/analyze')) {
                return Promise.resolve(
                    createResponse({
                        overview: 'Valid overview of the article.',
                        key_insights: [
                            'Insight one',
                            'Insight two',
                            'Insight three',
                        ],
                        outstaffer_opportunity: 'A clear opportunity description.',
                    }),
                );
            }
            if (url.endsWith('/synthesize')) {
                return Promise.resolve(createResponse({ error: 'Not used in this test' }, { status: 500 }));
            }
            return Promise.resolve(createResponse({}));
        });

        global.fetch = fetchMock as unknown as typeof fetch;

        render(<ContentFinder />);

        await userEvent.type(screen.getByLabelText(/Search Query/i), 'remote work');
        await userEvent.click(screen.getByRole('button', { name: /search/i }));

        await waitFor(() => expect(screen.getByText(/Search Results/i)).toBeInTheDocument());

        const processButton = screen.getByRole('button', { name: /Process/i });
        await userEvent.click(processButton);

        await waitFor(() => expect(screen.getByText('Overview')).toBeInTheDocument());
        expect(screen.getByText('Valid overview of the article.')).toBeInTheDocument();
        expect(screen.getByText('Copy JSON')).toBeInTheDocument();
    });

    it('shows a validation error badge when structured payload fails validation', async () => {
        const fetchMock = vi.fn((input: RequestInfo | URL) => {
            const url = typeof input === 'string' ? input : input.toString();
            if (url.endsWith('/search')) {
                return Promise.resolve(
                    createResponse({
                        results: [
                            {
                                url: 'https://invalid.example/article-2',
                                title: 'Invalid Article',
                                description: 'An invalid response example',
                            },
                        ],
                    }),
                );
            }
            if (url.endsWith('/scrape')) {
                return Promise.resolve(
                    createResponse({
                        results: [
                            {
                                url: 'https://invalid.example/article-2',
                                title: 'Invalid Article',
                                markdown: '# Heading\n\nContent',
                                success: true,
                            },
                        ],
                    }),
                );
            }
            if (url.endsWith('/analyze')) {
                return Promise.resolve(createResponse({ overview: 'Missing keys' }));
            }
            if (url.endsWith('/synthesize')) {
                return Promise.resolve(createResponse({ error: 'Not used in this test' }, { status: 500 }));
            }
            return Promise.resolve(createResponse({}));
        });

        global.fetch = fetchMock as unknown as typeof fetch;

        render(<ContentFinder />);

        await userEvent.type(screen.getByLabelText(/Search Query/i), 'staffing strategies');
        await userEvent.click(screen.getByRole('button', { name: /search/i }));

        await waitFor(() => expect(screen.getByText(/Search Results/i)).toBeInTheDocument());

        const processButton = screen.getByRole('button', { name: /Process/i });
        await userEvent.click(processButton);

        const validationChip = await screen.findByText(/Validation error/i);
        expect(validationChip).toHaveTextContent(/Expected an array of strings/i);
    });
});
