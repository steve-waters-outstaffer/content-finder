import React from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Box,
    Chip,
    Link,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { CustomColors, FontWeight } from '../../../theme';

const groupBySubreddit = (posts = []) =>
    posts.reduce((acc, post) => {
        const subreddit = post.subreddit || 'unknown';
        if (!acc[subreddit]) acc[subreddit] = [];
        acc[subreddit].push(post);
        return acc;
    }, {});

const PreScoreResults = ({ stepInfo }) => {
    const posts = stepInfo?.data || [];
    const stats = stepInfo?.stats;
    const threshold = stepInfo?.threshold ?? 0;
    const groups = groupBySubreddit(posts);

    return (
        <Box>
            <Typography variant="h6" fontWeight={FontWeight.Medium} gutterBottom>
                Pre-Score Results
            </Typography>

            {stats && (
                <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
                    <Chip label={`${stats.input} Input Posts`} sx={{ bgcolor: CustomColors.UIGrey400 }} />
                    <Chip
                        label={`${stats.promising} Passed (≥${threshold})`}
                        sx={{ bgcolor: CustomColors.SecretGarden + '20' }}
                    />
                    <Chip label={`${stats.rejected} Rejected`} sx={{ bgcolor: CustomColors.UIGrey300 }} />
                </Stack>
            )}

            <Typography variant="subtitle1" fontWeight={FontWeight.SemiBold} gutterBottom>
                High-Scoring Posts ({posts.length})
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                These posts scored ≥{threshold} and will move to enrichment
            </Typography>

            {Object.entries(groups).map(([subreddit, subredditPosts]) => (
                <Accordion key={subreddit} sx={{ mb: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Stack direction="row" spacing={2} alignItems="center">
                            <Typography fontWeight={FontWeight.SemiBold}>r/{subreddit}</Typography>
                            <Chip label={`${subredditPosts.length} posts`} size="small" sx={{ bgcolor: CustomColors.SecretGarden + '20' }} />
                        </Stack>
                    </AccordionSummary>
                    <AccordionDetails>
                        <TableContainer>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Title</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>
                                            Score
                                        </TableCell>
                                        <TableCell align="right" sx={{ fontWeight: FontWeight.SemiBold }}>
                                            AI Score
                                        </TableCell>
                                        <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Reason</TableCell>
                                        <TableCell sx={{ fontWeight: FontWeight.SemiBold }}>Link</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {subredditPosts.map((post) => (
                                        <TableRow key={post.id} hover>
                                            <TableCell sx={{ maxWidth: 300 }}>
                                                <Typography
                                                    variant="body2"
                                                    sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                                    title={post.title}
                                                >
                                                    {post.title}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right">
                                                <Typography variant="body2">{post.score?.toLocaleString() || 0}</Typography>
                                            </TableCell>
                                            <TableCell align="right">
                                                <Chip
                                                    label={post.prescore?.relevance_score?.toFixed(1) || 'N/A'}
                                                    size="small"
                                                    sx={{
                                                        bgcolor:
                                                            post.prescore?.relevance_score >= threshold
                                                                ? CustomColors.SecretGarden + '40'
                                                                : CustomColors.UIGrey300,
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell sx={{ maxWidth: 300 }}>
                                                <Typography
                                                    variant="body2"
                                                    sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                                    title={post.prescore?.quick_reason}
                                                >
                                                    {post.prescore?.quick_reason || 'No reason provided'}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                {post.permalink ? (
                                                    <Link
                                                        href={`https://reddit.com${post.permalink}`}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        variant="body2"
                                                    >
                                                        Reddit
                                                    </Link>
                                                ) : (
                                                    <Typography variant="body2" color="text.secondary">
                                                        No link
                                                    </Typography>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </AccordionDetails>
                </Accordion>
            ))}
        </Box>
    );
};

export default PreScoreResults;
