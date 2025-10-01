// src/components/intelligence/VOCDiscovery.jsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Checkbox,
    Chip,
    CircularProgress,
    Divider,
    FormControlLabel,
    Grid,
    Stack,
    TextField,
    Typography,
    MenuItem,
    Paper,
    Link,
    Stepper,
    Step,
    StepLabel,
    StepContent,
} from '@mui/material';
import InsightsIcon from '@mui/icons-material/Insights';
import ForumIcon from '@mui/icons-material/Forum';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import { CustomColors, FontWeight } from '../../theme';

const DEFAULT_API_BASE = 'https://content-finder-backend-4ajpjhwlsq-ts.a.run.app';
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || DEFAULT_API_BASE;

const defaultSegments = ['SMB Leaders'];

const PostCard = ({ post, isGreyedOut, onToggle, isSelected, showAnalysis }) => (
    <Card
        variant="outlined"
        sx={{
            mb: 2,
            opacity: isGreyedOut ? 0.5 : 1,
            transition: 'opacity 0.3s',
        }}
    >
        <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                {onToggle && (
                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={Boolean(isSelected)}
                                onChange={() => onToggle(post.id)}
                            />
                        }
                        label=""
                        sx={{ mr: 1, mt: -1 }}
                    />
                )}
                <Box flexGrow={1}>
                    <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                        {post.title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        r/{post.subreddit} • Score {post.score} • {post.num_comments} comments
                    </Typography>
                    {post.content_snippet && (
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            {post.content_snippet}
                        </Typography>
                    )}
                    {showAnalysis && post.ai_analysis && (
                        <Box sx={{ mt: 2, p: 2, bgcolor: CustomColors.UIGrey100, borderRadius: 1 }}>
                            <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold} gutterBottom>
                                AI Insight
                            </Typography>
                            <Typography variant="body2">
                                <strong>Relevance:</strong> {post.ai_analysis.relevance_score ?? 'n/a'}
                            </Typography>
                            {post.ai_analysis.identified_pain_point && (
                                <Typography variant="body2" sx={{ mt: 0.5 }}>
                                    <strong>Pain Point:</strong> {post.ai_analysis.identified_pain_point}
                                </Typography>
                            )}
                            {post.ai_analysis.reasoning && (
                                <Typography variant="body2" sx={{ mt: 0.5 }} color="text.secondary">
                                    {post.ai_analysis.reasoning}
                                </Typography>
                            )}
                        </Box>
                    )}
                    {post.url && (
                        <Typography variant="body2" sx={{ mt: 1 }}>
                            <Link href={post.url} target="_blank" rel="noreferrer">
                                View discussion
                            </Link>
                        </Typography>
                    )}
                </Box>
            </Stack>
        </CardContent>
    </Card>
);

const VOCDiscovery = () => {
    const [segmentName, setSegmentName] = useState(defaultSegments[0]);
    const [availableSegments, setAvailableSegments] = useState(defaultSegments);
    const [error, setError] = useState('');
    const [warnings, setWarnings] = useState([]);
    
    // Stage data
    const [rawPosts, setRawPosts] = useState([]);
    const [filteredPosts, setFilteredPosts] = useState([]);
    const [googleTrends, setGoogleTrends] = useState([]);
    const [curatedQueries, setCuratedQueries] = useState([]);
    
    // Stage control
    const [activeStep, setActiveStep] = useState(0);
    const [isLoading, setIsLoading] = useState(false);
    const [stageDurations, setStageDurations] = useState({});
    
    const [segmentConfig, setSegmentConfig] = useState(null);

    // Load available segments on mount
    useEffect(() => {
        const loadSegments = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/intelligence/config`);
                if (!response.ok) return;
                
                const config = await response.json();
                const segments = config?.monthly_run?.segments?.map((segment) => segment.name).filter(Boolean) || [];

                if (segments.length) {
                    setAvailableSegments(segments);
                    if (!segments.includes(segmentName)) {
                        setSegmentName(segments[0]);
                    }
                }
            } catch (configError) {
                console.warn('Unable to load intelligence segments:', configError);
            }
        };

        loadSegments();
    }, []);

    // Load segment config when segment changes
    useEffect(() => {
        setSegmentConfig(null);
        setActiveStep(0);
        setRawPosts([]);
        setFilteredPosts([]);
        setGoogleTrends([]);
        setCuratedQueries([]);
        setWarnings([]);
        setError('');
        setStageDurations({});

        if (!segmentName) return;

        let isCancelled = false;

        const fetchConfig = async () => {
            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/segment-config/${encodeURIComponent(segmentName)}`,
                );

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                if (!isCancelled) {
                    setSegmentConfig({
                        subreddits: Array.isArray(data.subreddits) ? data.subreddits : [],
                        trends_keywords: Array.isArray(data.trends_keywords) ? data.trends_keywords : [],
                    });
                }
            } catch (configError) {
                console.error('Failed to fetch segment config:', configError);
                if (!isCancelled) {
                    setSegmentConfig({ subreddits: [], trends_keywords: [] });
                }
            }
        };

        fetchConfig();

        return () => {
            isCancelled = true;
        };
    }, [segmentName]);

    // Stage 1: Fetch Reddit Posts
    const handleFetchReddit = async () => {
        if (!segmentName) return;

        setIsLoading(true);
        setError('');
        setWarnings([]);

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/fetch-reddit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ segment_name: segmentName }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setRawPosts(data.raw_posts || []);
            setWarnings(data.warnings || []);
            setStageDurations(prev => ({ ...prev, fetch: data.duration_ms }));
            setActiveStep(1);
        } catch (err) {
            console.error('Reddit fetch failed:', err);
            setError('Failed to fetch Reddit posts. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    // Stage 2: Analyze Posts
    const handleAnalyzePosts = async () => {
        setIsLoading(true);
        setError('');

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/analyze-posts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    segment_name: segmentName,
                    raw_posts: rawPosts,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setFilteredPosts(data.filtered_posts || []);
            setWarnings(prev => [...prev, ...(data.warnings || [])]);
            setStageDurations(prev => ({ ...prev, analyze: data.duration_ms }));
            setActiveStep(2);
        } catch (err) {
            console.error('Post analysis failed:', err);
            setError('Failed to analyze posts. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    // Stage 3: Fetch Trends
    const handleFetchTrends = async () => {
        setIsLoading(true);
        setError('');

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/fetch-trends`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ segment_name: segmentName }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setGoogleTrends(data.trends || []);
            setWarnings(prev => [...prev, ...(data.warnings || [])]);
            setStageDurations(prev => ({ ...prev, trends: data.duration_ms }));
            setActiveStep(3);
        } catch (err) {
            console.error('Trends fetch failed:', err);
            setError('Failed to fetch trends. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    // Stage 4: Generate Queries
    const handleGenerateQueries = async () => {
        setIsLoading(true);
        setError('');

        try {
            const response = await fetch(`${API_BASE_URL}/api/intelligence/voc-discovery/generate-queries`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    segment_name: segmentName,
                    filtered_posts: filteredPosts,
                    trends: googleTrends,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setCuratedQueries(data.queries || []);
            setStageDurations(prev => ({ ...prev, queries: data.duration_ms }));
            setActiveStep(4);
        } catch (err) {
            console.error('Query generation failed:', err);
            setError('Failed to generate queries. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSegmentChange = (event) => {
        setSegmentName(event.target.value);
    };

    const handleReset = () => {
        setActiveStep(0);
        setRawPosts([]);
        setFilteredPosts([]);
        setGoogleTrends([]);
        setCuratedQueries([]);
        setWarnings([]);
        setError('');
        setStageDurations({});
    };

    const steps = [
        {
            label: 'Fetch Reddit Posts',
            description: 'Collect posts from configured subreddits',
            action: handleFetchReddit,
            buttonLabel: 'Start Discovery',
            icon: <ForumIcon />,
        },
        {
            label: 'Analyze Posts',
            description: 'AI scoring and filtering for relevance',
            action: handleAnalyzePosts,
            buttonLabel: 'Analyze Posts',
            icon: <AutoAwesomeIcon />,
        },
        {
            label: 'Fetch Google Trends',
            description: 'Collect trending search data',
            action: handleFetchTrends,
            buttonLabel: 'Get Trends',
            icon: <TrendingUpIcon />,
        },
        {
            label: 'Generate Queries',
            description: 'Create curated research prompts',
            action: handleGenerateQueries,
            buttonLabel: 'Generate Queries',
            icon: <InsightsIcon />,
        },
    ];

    return (
        <Box>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'flex-end' }} mb={3}>
                <TextField
                    select
                    label="Audience Segment"
                    value={segmentName}
                    onChange={handleSegmentChange}
                    sx={{ minWidth: 220 }}
                    size="small"
                    disabled={activeStep > 0}
                >
                    {availableSegments.map((segment) => (
                        <MenuItem key={segment} value={segment}>
                            {segment}
                        </MenuItem>
                    ))}
                </TextField>

                {activeStep > 0 && (
                    <Button
                        variant="outlined"
                        onClick={handleReset}
                        size="small"
                    >
                        Reset
                    </Button>
                )}
            </Stack>

            {segmentConfig && activeStep === 0 && (
                <Card sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6" fontWeight={FontWeight.SemiBold} gutterBottom>
                            🔍 Discovery Configuration
                        </Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={12} md={6}>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                    Subreddits to Search
                                </Typography>
                                {segmentConfig.subreddits?.length ? (
                                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                        {segmentConfig.subreddits.map((subreddit) => (
                                            <Chip key={subreddit} label={`r/${subreddit}`} size="small" />
                                        ))}
                                    </Stack>
                                ) : (
                                    <Typography variant="body2" color="text.secondary">
                                        No subreddits configured
                                    </Typography>
                                )}
                            </Grid>
                            <Grid item xs={12} md={6}>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                    Google Trends Keywords
                                </Typography>
                                {segmentConfig.trends_keywords?.length ? (
                                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                                        {segmentConfig.trends_keywords.map((keyword) => (
                                            <Chip key={keyword} label={keyword} size="small" />
                                        ))}
                                    </Stack>
                                ) : (
                                    <Typography variant="body2" color="text.secondary">
                                        No keywords configured
                                    </Typography>
                                )}
                            </Grid>
                        </Grid>
                    </CardContent>
                </Card>
            )}

            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
            )}

            {warnings.length > 0 && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                    <Typography variant="body2" fontWeight={FontWeight.SemiBold}>
                        Warnings:
                    </Typography>
                    {warnings.map((warning, idx) => (
                        <Typography key={idx} variant="body2">
                            • {warning}
                        </Typography>
                    ))}
                </Alert>
            )}

            <Stepper activeStep={activeStep} orientation="vertical">
                {steps.map((step, index) => (
                    <Step key={step.label}>
                        <StepLabel icon={step.icon}>
                            <Stack direction="row" spacing={1} alignItems="center">
                                <Typography>{step.label}</Typography>
                                {stageDurations[Object.keys(stageDurations)[index]] && (
                                    <Chip
                                        label={`${(stageDurations[Object.keys(stageDurations)[index]] / 1000).toFixed(1)}s`}
                                        size="small"
                                        variant="outlined"
                                    />
                                )}
                            </Stack>
                        </StepLabel>
                        <StepContent>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                {step.description}
                            </Typography>

                            {/* Show results for completed steps */}
                            {index === 0 && rawPosts.length > 0 && (
                                <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: CustomColors.UIGrey50 }}>
                                    <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold}>
                                        📊 Raw Feed ({rawPosts.length} posts)
                                    </Typography>
                                    <Box sx={{ maxHeight: 200, overflow: 'auto', mt: 1 }}>
                                        {rawPosts.slice(0, 3).map((post) => (
                                            <PostCard key={post.id} post={post} showAnalysis={false} />
                                        ))}
                                        {rawPosts.length > 3 && (
                                            <Typography variant="body2" color="text.secondary">
                                                ...and {rawPosts.length - 3} more
                                            </Typography>
                                        )}
                                    </Box>
                                </Paper>
                            )}

                            {index === 1 && filteredPosts.length > 0 && (
                                <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: CustomColors.UIGrey50 }}>
                                    <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold}>
                                        ✨ AI Analysis ({filteredPosts.length} posts passed filters)
                                    </Typography>
                                    <Box sx={{ maxHeight: 300, overflow: 'auto', mt: 1 }}>
                                        {filteredPosts.slice(0, 2).map((post) => (
                                            <PostCard key={post.id} post={post} showAnalysis={true} />
                                        ))}
                                        {filteredPosts.length > 2 && (
                                            <Typography variant="body2" color="text.secondary">
                                                ...and {filteredPosts.length - 2} more
                                            </Typography>
                                        )}
                                    </Box>
                                </Paper>
                            )}

                            {index === 2 && googleTrends.length > 0 && (
                                <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: CustomColors.UIGrey50 }}>
                                    <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold}>
                                        📈 Google Trends ({googleTrends.length} keywords)
                                    </Typography>
                                    <Grid container spacing={1} sx={{ mt: 1 }}>
                                        {googleTrends.map((trend) => (
                                            <Grid item key={trend.keyword}>
                                                <Chip label={trend.keyword} size="small" />
                                            </Grid>
                                        ))}
                                    </Grid>
                                </Paper>
                            )}

                            {index === 3 && curatedQueries.length > 0 && (
                                <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: CustomColors.UIGrey50 }}>
                                    <Typography variant="subtitle2" fontWeight={FontWeight.SemiBold}>
                                        🎯 Curated Research Prompts ({curatedQueries.length})
                                    </Typography>
                                    <Stack spacing={1} sx={{ mt: 1 }}>
                                        {curatedQueries.map((query, idx) => (
                                            <Typography key={idx} variant="body2">
                                                • {query}
                                            </Typography>
                                        ))}
                                    </Stack>
                                </Paper>
                            )}

                            {/* Action button */}
                            {activeStep === index && (
                                <Button
                                    variant="contained"
                                    onClick={step.action}
                                    disabled={isLoading}
                                    startIcon={isLoading ? <CircularProgress size={20} /> : null}
                                >
                                    {isLoading ? 'Processing...' : step.buttonLabel}
                                </Button>
                            )}
                        </StepContent>
                    </Step>
                ))}
            </Stepper>

            {activeStep === steps.length && (
                <Paper variant="outlined" sx={{ p: 3, mt: 2 }}>
                    <Stack direction="row" spacing={2} alignItems="center" mb={2}>
                        <TaskAltIcon color="success" />
                        <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
                            Discovery Complete!
                        </Typography>
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                        Total time: {(Object.values(stageDurations).reduce((a, b) => a + b, 0) / 1000).toFixed(1)}s
                    </Typography>
                    <Button onClick={handleReset} sx={{ mt: 2 }}>
                        Start New Discovery
                    </Button>
                </Paper>
            )}
        </Box>
    );
};

export default VOCDiscovery;
