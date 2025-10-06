import type { JSX } from 'react';
import { useMemo, useState } from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Checkbox,
    Chip,
    CircularProgress,
    FormControl,
    InputLabel,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import {
    Assignment as AssignmentIcon,
    CheckCircle as CheckCircleIcon,
    ExpandMore as ExpandMoreIcon,
    Link as LinkIcon,
    Psychology as PsychologyIcon,
    Search as SearchIcon,
    TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';

import { ArticleAnalysis, MultiArticleAnalysis } from '../types/intelligence';
import { CustomColors, FontWeight } from '../theme';

interface SearchResultItem {
    url: string;
    title?: string;
    description?: string;
    [key: string]: unknown;
}

interface SearchResponse {
    query: string;
    steps: {
        search: {
            results: SearchResultItem[];
        };
    };
}

interface ScrapeResultEntry {
    url: string;
    title?: string;
    markdown?: string;
    success?: boolean;
    [key: string]: unknown;
}

interface ScrapeResponse {
    results: ScrapeResultEntry[];
}

type ProcessingStage = 'scraping' | 'analyzing' | 'completed' | 'error';

type ProcessingStatusMap = Record<string, ProcessingStage | undefined>;

type RatingMap = Record<string, number>;

interface ProcessedResultEntry {
    scrape?: ScrapeResultEntry;
    analysis?: ArticleAnalysis;
    validationError?: string | null;
    error?: string;
    processedAt: string;
}

const API_BASE = 'https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api';

const ARTICLE_ANALYSIS_KEYS = new Set(['overview', 'key_insights', 'outstaffer_opportunity']);
const MULTI_ANALYSIS_KEYS = new Set(['overview', 'key_insights', 'outstaffer_opportunity', 'cross_article_themes']);

const formatValidationError = (path: string, message: string): string => `${path}: ${message}`;

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
    Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const validateArticleAnalysis = (
    payload: unknown,
): { value?: ArticleAnalysis; error?: string } => {
    if (!isPlainObject(payload)) {
        return { error: formatValidationError('root', 'Expected an object payload') };
    }

    for (const key of Object.keys(payload)) {
        if (!ARTICLE_ANALYSIS_KEYS.has(key)) {
            return { error: formatValidationError(key, 'Unexpected field') };
        }
    }

    const overview = payload.overview;
    if (typeof overview !== 'string' || !overview.trim()) {
        return { error: formatValidationError('overview', 'Expected a non-empty string') };
    }

    const keyInsights = payload.key_insights;
    if (!Array.isArray(keyInsights)) {
        return { error: formatValidationError('key_insights', 'Expected an array of strings') };
    }
    if (keyInsights.length === 0) {
        return { error: formatValidationError('key_insights', 'Must include at least one insight') };
    }
    const sanitizedInsights: string[] = [];
    for (let index = 0; index < keyInsights.length; index += 1) {
        const insight = keyInsights[index];
        if (typeof insight !== 'string' || !insight.trim()) {
            return { error: formatValidationError(`key_insights[${index}]`, 'Expected a non-empty string') };
        }
        sanitizedInsights.push(insight);
    }

    const opportunity = payload.outstaffer_opportunity;
    if (typeof opportunity !== 'string' || !opportunity.trim()) {
        return { error: formatValidationError('outstaffer_opportunity', 'Expected a non-empty string') };
    }

    return {
        value: {
            overview,
            key_insights: sanitizedInsights,
            outstaffer_opportunity: opportunity,
        },
    };
};

const validateMultiArticleAnalysis = (
    payload: unknown,
): { value?: MultiArticleAnalysis; error?: string } => {
    if (!isPlainObject(payload)) {
        return { error: formatValidationError('root', 'Expected an object payload') };
    }

    for (const key of Object.keys(payload)) {
        if (!MULTI_ANALYSIS_KEYS.has(key)) {
            return { error: formatValidationError(key, 'Unexpected field') };
        }
    }

    const baseValidation = validateArticleAnalysis({
        overview: payload.overview,
        key_insights: payload.key_insights,
        outstaffer_opportunity: payload.outstaffer_opportunity,
    });

    if (baseValidation.error) {
        return { error: baseValidation.error };
    }

    const crossThemesRaw = payload.cross_article_themes;
    let crossThemes: string[] = [];
    if (crossThemesRaw !== undefined) {
        if (!Array.isArray(crossThemesRaw)) {
            return { error: formatValidationError('cross_article_themes', 'Expected an array of strings') };
        }
        crossThemes = [];
        for (let index = 0; index < crossThemesRaw.length; index += 1) {
            const theme = crossThemesRaw[index];
            if (typeof theme !== 'string' || !theme.trim()) {
                return { error: formatValidationError(`cross_article_themes[${index}]`, 'Expected a non-empty string') };
            }
            crossThemes.push(theme);
        }
    }

    return {
        value: {
            ...baseValidation.value!,
            cross_article_themes: crossThemes,
        },
    };
};

const createFilenameFromUrl = (url: string, suffix: string): string => {
    try {
        const hostname = new URL(url).hostname.replace(/[^a-z0-9]+/gi, '-');
        return `${hostname}-${suffix}.json`;
    } catch (err) {
        return `analysis-${suffix}.json`;
    }
};

const ContentFinder = (): JSX.Element => {
    const [searchQuery, setSearchQuery] = useState<string>('');
    const [searchLimit, setSearchLimit] = useState<number>(5);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [results, setResults] = useState<SearchResponse | null>(null);
    const [error, setError] = useState<string>('');
    const [processingUrls, setProcessingUrls] = useState<Set<string>>(new Set());
    const [processedResults, setProcessedResults] = useState<Record<string, ProcessedResultEntry>>({});
    const [processingStatus, setProcessingStatus] = useState<ProcessingStatusMap>({});
    const [sourceRatings, setSourceRatings] = useState<RatingMap>({});
    const [contentRatings, setContentRatings] = useState<RatingMap>({});
    const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
    const [isSynthesizing, setIsSynthesizing] = useState<boolean>(false);
    const [synthesisResult, setSynthesisResult] = useState<MultiArticleAnalysis | null>(null);
    const [synthesisValidationError, setSynthesisValidationError] = useState<string | null>(null);

    const curatedTerms = [
        'SMB hiring challenges 2025',
        'APAC talent recruitment trends',
        'EOR global hiring benefits',
        'AI in staffing industry',
    ];

    const resetProcessingState = () => {
        setProcessedResults({});
        setSelectedUrls(new Set());
        setProcessingUrls(new Set());
        setProcessingStatus({});
        setSourceRatings({});
        setContentRatings({});
        setSynthesisResult(null);
        setSynthesisValidationError(null);
    };

    const handleSearch = async () => {
        if (!searchQuery.trim()) {
            setError('Please enter a search query');
            return;
        }

        setIsLoading(true);
        setError('');
        resetProcessingState();

        try {
            const response = await fetch(`${API_BASE}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: searchQuery, limit: searchLimit }),
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }

            const searchData = await response.json();
            const normalized: SearchResponse = {
                query: searchQuery,
                steps: {
                    search: {
                        results: Array.isArray(searchData?.results)
                            ? (searchData.results as SearchResultItem[])
                            : [],
                    },
                },
            };
            setResults(normalized);
        } catch (err) {
            setError(`Failed to search: ${(err as Error).message}`);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCuratedTermClick = (term: string) => {
        setSearchQuery(term);
    };

    const handleSourceRating = (url: string, rating: number) => {
        setSourceRatings((prev) => ({ ...prev, [url]: rating }));
        console.log(`⭐ Source rated: ${url} = ${rating} stars`);
    };

    const handleContentRating = (url: string, rating: number) => {
        setContentRatings((prev) => ({ ...prev, [url]: rating }));
        console.log(`🤖 Analysis rated: ${url} = ${rating} stars`);
    };

    const renderStarRating = (currentRating: number | undefined, onRate: (rating: number) => void, label: string) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="caption">{label}:</Typography>
            <Box sx={{ display: 'flex', gap: 0.2 }}>
                {[1, 2, 3, 4, 5].map((star) => (
                    <Typography
                        key={star}
                        onClick={() => onRate(star)}
                        sx={{
                            cursor: 'pointer',
                            fontSize: '16px',
                            '&:hover': {
                                opacity: 0.7,
                                transform: 'scale(1.1)',
                            },
                            transition: 'all 0.2s',
                        }}
                    >
                        {star <= (currentRating || 0) ? '⭐' : '☆'}
                    </Typography>
                ))}
            </Box>
            <Typography variant="caption" color="text.secondary">
                {currentRating ? `(${currentRating}/5)` : '(Optional)'}
            </Typography>
        </Box>
    );

    const copyJsonToClipboard = async (payload: unknown) => {
        if (!navigator.clipboard) {
            setError('Clipboard access is not available in this browser.');
            return;
        }
        try {
            await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
        } catch (err) {
            setError(`Failed to copy JSON: ${(err as Error).message}`);
        }
    };

    const exportJson = (payload: unknown, filename: string) => {
        try {
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = filename;
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
            URL.revokeObjectURL(url);
        } catch (err) {
            setError(`Failed to export JSON: ${(err as Error).message}`);
        }
    };

    const handleProcessUrl = async (url: string) => {
        if (processingUrls.has(url)) {
            return;
        }

        setProcessingUrls((prev) => new Set(prev).add(url));
        setProcessingStatus((prev) => ({ ...prev, [url]: 'scraping' }));
        setError('');

        try {
            const scrapeResponse = await fetch(`${API_BASE}/scrape`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls: [url] }),
            });

            if (!scrapeResponse.ok) {
                throw new Error(`Scraping failed: ${scrapeResponse.status}`);
            }

            const scrapeData: ScrapeResponse = await scrapeResponse.json();
            const scrapeResult = scrapeData.results[0];

            if (!scrapeResult || !scrapeResult.success || !scrapeResult.markdown) {
                throw new Error(scrapeResult?.error as string || 'Scraping failed');
            }

            setProcessingStatus((prev) => ({ ...prev, [url]: 'analyzing' }));

            const analysisResponse = await fetch(`${API_BASE}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: scrapeResult.markdown }),
            });

            const analysisPayload = await analysisResponse.json();
            if (!analysisResponse.ok) {
                throw new Error((analysisPayload && analysisPayload.error) || 'AI analysis failed');
            }

            const validation = validateArticleAnalysis(analysisPayload);

            setProcessedResults((prev) => ({
                ...prev,
                [url]: {
                    scrape: scrapeResult,
                    analysis: validation.value,
                    validationError: validation.error ?? null,
                    processedAt: new Date().toISOString(),
                },
            }));
            setProcessingStatus((prev) => ({ ...prev, [url]: 'completed' }));
        } catch (err) {
            setProcessedResults((prev) => ({
                ...prev,
                [url]: { error: (err as Error).message, processedAt: new Date().toISOString() },
            }));
            setProcessingStatus((prev) => ({ ...prev, [url]: 'error' }));
        } finally {
            setProcessingUrls((prev) => {
                const next = new Set(prev);
                next.delete(url);
                return next;
            });
        }
    };

    const handleUrlSelection = (url: string, isSelected: boolean) => {
        setSelectedUrls((prev) => {
            const next = new Set(prev);
            if (isSelected) {
                next.add(url);
            } else {
                next.delete(url);
            }
            return next;
        });
    };

    const handleSynthesizeSelected = async () => {
        if (selectedUrls.size === 0) {
            setError('Please select at least one article to synthesize.');
            return;
        }

        setIsSynthesizing(true);
        setError('');
        setSynthesisResult(null);
        setSynthesisValidationError(null);

        try {
            const scrapeResponse = await fetch(`${API_BASE}/scrape`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls: Array.from(selectedUrls) }),
            });

            if (!scrapeResponse.ok) {
                throw new Error('Failed to scrape content for synthesis.');
            }

            const scrapeData: ScrapeResponse = await scrapeResponse.json();
            const successfulScrapes = scrapeData.results.filter((result) => result.success && result.markdown);

            if (successfulScrapes.length === 0) {
                throw new Error('Could not retrieve content from any of the selected URLs.');
            }

            const synthesisResponse = await fetch(`${API_BASE}/synthesize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: searchQuery,
                    contents: successfulScrapes.map((scrape) => ({
                        url: scrape.url,
                        title: scrape.title,
                        markdown: scrape.markdown,
                    })),
                }),
            });

            const synthesisPayload = await synthesisResponse.json();
            if (!synthesisResponse.ok) {
                throw new Error((synthesisPayload && synthesisPayload.error) || 'The AI failed to synthesize the article.');
            }

            const validation = validateMultiArticleAnalysis(synthesisPayload);
            setSynthesisValidationError(validation.error ?? null);
            if (validation.value) {
                setSynthesisResult({ ...validation.value, cross_article_themes: validation.value.cross_article_themes ?? [] });
            } else {
                setSynthesisResult(null);
            }
        } catch (err) {
            setError(`Synthesis failed: ${(err as Error).message}`);
        } finally {
            setIsSynthesizing(false);
        }
    };

    const searchResults = useMemo(() => results?.steps?.search?.results ?? [], [results]);

    const renderSearchResults = () => {
        if (!searchResults.length) {
            return null;
        }

        return (
            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                        <Typography variant="h6" gutterBottom>
                            <SearchIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                            Search Results ({searchResults.length} found)
                        </Typography>
                        <Button
                            variant="contained"
                            color="secondary"
                            disabled={selectedUrls.size === 0 || isSynthesizing}
                            onClick={handleSynthesizeSelected}
                            startIcon={isSynthesizing ? <CircularProgress size={16} /> : <PsychologyIcon />}
                        >
                            {isSynthesizing ? 'Synthesizing...' : `Synthesize (${selectedUrls.size}) Articles`}
                        </Button>
                    </Box>

                    {searchResults.map((result) => {
                        const isProcessing = processingUrls.has(result.url);
                        const processedData = processedResults[result.url];
                        const hasBeenProcessed = Boolean(processedData);
                        const currentStatus = processingStatus[result.url];

                        return (
                            <Paper
                                key={result.url}
                                elevation={0}
                                sx={{
                                    p: 2,
                                    mb: 1,
                                    border: `2px solid ${hasBeenProcessed ? (processedData?.error ? CustomColors.DarkRed : CustomColors.SecretGarden) : CustomColors.UIGrey300}`,
                                    borderRadius: 2,
                                    backgroundColor: 'white',
                                }}
                            >
                                <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                                    <Checkbox
                                        checked={selectedUrls.has(result.url)}
                                        onChange={(event) => handleUrlSelection(result.url, event.target.checked)}
                                        sx={{ mt: 1.5, mr: 1 }}
                                    />
                                    <Box sx={{ flex: 1 }}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                            <Box sx={{ flex: 1 }}>
                                                <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                                                    {result.title || 'Untitled Result'}
                                                </Typography>
                                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                                    {result.description || 'No description available'}
                                                </Typography>
                                                <Typography
                                                    variant="caption"
                                                    sx={{ color: CustomColors.DeepSkyBlue, textDecoration: 'underline', cursor: 'pointer' }}
                                                    onClick={() => window.open(result.url, '_blank')}
                                                >
                                                    <LinkIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                                                    {result.url}
                                                </Typography>
                                                <Box sx={{ mt: 1 }}>
                                                    {renderStarRating(sourceRatings[result.url], (rating) => handleSourceRating(result.url, rating), 'Source Quality')}
                                                </Box>
                                                {(isProcessing || hasBeenProcessed) && (
                                                    <Box sx={{ mt: 1 }}>
                                                        {isProcessing && (
                                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                                <CircularProgress size={16} />
                                                                <Typography variant="caption" color="primary">
                                                                    {currentStatus === 'scraping' && '📄 Scraping content...'}
                                                                    {currentStatus === 'analyzing' && '🤖 Analyzing with AI...'}
                                                                </Typography>
                                                            </Box>
                                                        )}
                                                        {hasBeenProcessed && !isProcessing && (
                                                            <Box>
                                                                {processedData?.error ? (
                                                                    <Typography variant="caption" color="error">
                                                                        ❌ Failed: {processedData.error}
                                                                    </Typography>
                                                                ) : (
                                                                    <Typography variant="caption" color="success.main">
                                                                        ✅ Processed successfully
                                                                    </Typography>
                                                                )}
                                                            </Box>
                                                        )}
                                                    </Box>
                                                )}
                                            </Box>
                                            <Box sx={{ ml: 2 }}>
                                                <Button
                                                    variant={hasBeenProcessed ? 'outlined' : 'contained'}
                                                    color={hasBeenProcessed ? 'secondary' : 'primary'}
                                                    size="small"
                                                    onClick={() => handleProcessUrl(result.url)}
                                                    disabled={isProcessing}
                                                    sx={{ minWidth: 100 }}
                                                >
                                                    {isProcessing
                                                        ? currentStatus === 'scraping'
                                                            ? 'Scraping...'
                                                            : 'Analyzing...'
                                                        : hasBeenProcessed
                                                        ? processedData?.error
                                                            ? 'Retry'
                                                            : 'Reprocess'
                                                        : 'Process'}
                                                </Button>
                                            </Box>
                                        </Box>
                                    </Box>
                                </Box>
                            </Paper>
                        );
                    })}
                </CardContent>
            </Card>
        );
    };

    const renderAnalysisEntries = () => {
        const entries = Object.entries(processedResults).filter(([, entry]) => Boolean(entry.scrape));
        if (!entries.length) {
            return null;
        }

        return (
            <Card sx={{ mb: 2 }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        <PsychologyIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        Individual AI Analysis ({entries.length} insights)
                    </Typography>
                    {entries.map(([url, data], index) => {
                        const articleTitle = data.scrape?.title || `Article ${index + 1}`;
                        const analysis = data.analysis;
                        return (
                            <Accordion key={url} defaultExpanded sx={{ mb: 1 }}>
                                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                    <Box>
                                        <Typography variant="subtitle2" fontWeight={FontWeight.Medium}>
                                            Analysis for {(() => {
                                                try {
                                                    return new URL(url).hostname;
                                                } catch (err) {
                                                    return url;
                                                }
                                            })()}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary" display="block">
                                            {articleTitle}
                                        </Typography>
                                    </Box>
                                </AccordionSummary>
                                <AccordionDetails sx={{ pt: 0 }}>
                                    {data.validationError && (
                                        <Chip
                                            color="error"
                                            label={`Validation error: ${data.validationError}`}
                                            size="small"
                                            sx={{ mb: 1 }}
                                        />
                                    )}
                                    {analysis ? (
                                        <Stack spacing={2} sx={{ bgcolor: CustomColors.UIGrey100, p: 2, borderRadius: 1 }}>
                                            <Box>
                                                <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold} gutterBottom>
                                                    Overview
                                                </Typography>
                                                <Typography variant="body2" color="text.primary">
                                                    {analysis.overview}
                                                </Typography>
                                            </Box>
                                            <Box>
                                                <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold} gutterBottom>
                                                    Key Insights
                                                </Typography>
                                                <List dense>
                                                    {analysis.key_insights.map((insight, insightIndex) => (
                                                        <ListItem key={insightIndex} disablePadding sx={{ alignItems: 'flex-start' }}>
                                                            <ListItemIcon sx={{ minWidth: 28, mt: 0.5 }}>
                                                                <CheckCircleIcon fontSize="small" color="primary" />
                                                            </ListItemIcon>
                                                            <ListItemText primaryTypographyProps={{ variant: 'body2' }} primary={insight} />
                                                        </ListItem>
                                                    ))}
                                                </List>
                                            </Box>
                                            <Box>
                                                <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold} gutterBottom>
                                                    Outstaffer Opportunity
                                                </Typography>
                                                <Typography variant="body2" color="text.primary">
                                                    {analysis.outstaffer_opportunity}
                                                </Typography>
                                            </Box>
                                            <Stack direction="row" spacing={1}>
                                                <Button
                                                    variant="text"
                                                    size="small"
                                                    onClick={() => copyJsonToClipboard(analysis)}
                                                >
                                                    Copy JSON
                                                </Button>
                                                <Button
                                                    variant="text"
                                                    size="small"
                                                    onClick={() => exportJson(analysis, createFilenameFromUrl(url, 'analysis'))}
                                                >
                                                    Export JSON
                                                </Button>
                                            </Stack>
                                            {renderStarRating(contentRatings[url], (rating) => handleContentRating(url, rating), 'Analysis Usefulness')}
                                        </Stack>
                                    ) : (
                                        <Typography variant="body2" color="text.secondary">
                                            Structured analysis unavailable.
                                        </Typography>
                                    )}
                                </AccordionDetails>
                            </Accordion>
                        );
                    })}
                </CardContent>
            </Card>
        );
    };

    const renderSynthesisResult = () => {
        if (!synthesisResult && !synthesisValidationError) {
            return null;
        }

        return (
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Accordion defaultExpanded>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            sx={{ bgcolor: CustomColors.UIGrey100, borderRadius: 1 }}
                        >
                            <Typography variant="h6">
                                <AssignmentIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                                Synthesized Research Overview
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails sx={{ pt: 2 }}>
                            {synthesisValidationError && (
                                <Chip
                                    color="error"
                                    label={`Validation error: ${synthesisValidationError}`}
                                    size="small"
                                    sx={{ mb: 2 }}
                                />
                            )}
                            {synthesisResult ? (
                                <Stack spacing={2}>
                                    <Box>
                                        <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                                            Overview
                                        </Typography>
                                        <Typography variant="body2" color="text.primary">
                                            {synthesisResult.overview}
                                        </Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                                            Key Insights
                                        </Typography>
                                        <List>
                                            {synthesisResult.key_insights.map((insight, index) => (
                                                <ListItem key={index} disablePadding sx={{ alignItems: 'flex-start' }}>
                                                    <ListItemIcon sx={{ minWidth: 28, mt: 0.5 }}>
                                                        <CheckCircleIcon fontSize="small" color="secondary" />
                                                    </ListItemIcon>
                                                    <ListItemText primaryTypographyProps={{ variant: 'body2' }} primary={insight} />
                                                </ListItem>
                                            ))}
                                        </List>
                                    </Box>
                                    <Box>
                                        <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                                            Outstaffer Opportunity
                                        </Typography>
                                        <Typography variant="body2" color="text.primary">
                                            {synthesisResult.outstaffer_opportunity}
                                        </Typography>
                                    </Box>
                                    {synthesisResult.cross_article_themes?.length ? (
                                        <Box>
                                            <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                                                Themes
                                            </Typography>
                                            <List>
                                                {synthesisResult.cross_article_themes.map((theme, index) => (
                                                    <ListItem key={index} disablePadding>
                                                        <ListItemIcon sx={{ minWidth: 28 }}>
                                                            <TrendingUpIcon fontSize="small" color="action" />
                                                        </ListItemIcon>
                                                        <ListItemText primaryTypographyProps={{ variant: 'body2' }} primary={theme} />
                                                    </ListItem>
                                                ))}
                                            </List>
                                        </Box>
                                    ) : null}
                                    <Stack direction="row" spacing={1}>
                                        {synthesisResult && (
                                            <>
                                                <Button
                                                    variant="text"
                                                    size="small"
                                                    onClick={() => copyJsonToClipboard(synthesisResult)}
                                                >
                                                    Copy JSON
                                                </Button>
                                                <Button
                                                    variant="text"
                                                    size="small"
                                                    onClick={() =>
                                                        exportJson(
                                                            synthesisResult,
                                                            `synthesis-${Date.now()}.json`,
                                                        )
                                                    }
                                                >
                                                    Export JSON
                                                </Button>
                                            </>
                                        )}
                                    </Stack>
                                </Stack>
                            ) : (
                                <Typography variant="body2" color="text.secondary">
                                    Structured synthesis unavailable due to validation failure.
                                </Typography>
                            )}
                        </AccordionDetails>
                    </Accordion>
                </CardContent>
            </Card>
        );
    };

    return (
        <Box sx={{ maxWidth: '100%' }}>
            <Card sx={{ mb: 3 }}>
                <CardContent>
                    <Typography variant="h5" gutterBottom fontWeight={FontWeight.SemiBold}>
                        Quick Research Tool
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        Search any topic, scrape and analyze multiple sources, then synthesize findings into structured briefs.
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, mb: 2, mt: 2 }}>
                        <TextField
                            fullWidth
                            variant="outlined"
                            label="Search Query"
                            placeholder="Enter search terms (e.g., 'SMB hiring trends 2025')"
                            value={searchQuery}
                            onChange={(event) => setSearchQuery(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === 'Enter') {
                                    handleSearch();
                                }
                            }}
                            disabled={isLoading}
                        />
                        <FormControl sx={{ minWidth: 120 }}>
                            <InputLabel>Results</InputLabel>
                            <Select
                                value={searchLimit}
                                label="Results"
                                onChange={(event) => setSearchLimit(Number(event.target.value))}
                                disabled={isLoading}
                            >
                                {[1, 2, 3, 5, 7, 10].map((num) => (
                                    <MenuItem key={num} value={num}>
                                        {num}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={handleSearch}
                            disabled={isLoading || !searchQuery.trim()}
                            sx={{ minWidth: 120 }}
                        >
                            {isLoading ? <CircularProgress size={24} color="inherit" /> : 'Search'}
                        </Button>
                    </Box>
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            Quick searches:
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                            {curatedTerms.map((term) => (
                                <Chip
                                    key={term}
                                    label={term}
                                    onClick={() => handleCuratedTermClick(term)}
                                    variant="outlined"
                                    size="medium"
                                    sx={{
                                        cursor: 'pointer',
                                        borderRadius: '20px',
                                        borderColor: CustomColors.DeepSkyBlue,
                                        color: CustomColors.DeepSkyBlue,
                                        fontWeight: FontWeight.Medium,
                                        '&:hover': {
                                            backgroundColor: CustomColors.AliceBlue,
                                            borderColor: CustomColors.MidnightBlue,
                                            color: CustomColors.MidnightBlue,
                                        },
                                    }}
                                />
                            ))}
                        </Box>
                    </Box>
                    {error && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {error}
                        </Alert>
                    )}
                </CardContent>
            </Card>
            {renderSearchResults()}
            {renderAnalysisEntries()}
            {renderSynthesisResult()}
        </Box>
    );
};

export default ContentFinder;
