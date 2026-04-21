#!/bin/bash
# Seed WordPress with test content for migration experiment
set -e

WP="docker compose exec -T wordpress"

echo "=== Installing WP-CLI ==="
docker compose exec -T wordpress bash -c "curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && mv wp-cli.phar /usr/local/bin/wp"

echo "=== Installing WordPress ==="
$WP wp core install \
  --url="http://localhost:8080" \
  --title="Migration Test Site" \
  --admin_user=admin \
  --admin_password=admin123 \
  --admin_email=admin@test.com \
  --allow-root

echo "=== Creating additional user ==="
$WP wp user create editor editor@test.com \
  --role=editor \
  --user_pass=editor123 \
  --display_name="Maria Rossi" \
  --allow-root

echo "=== Creating categories ==="
$WP wp term create category "Technology" --description="Posts about technology" --allow-root
$WP wp term create category "Science" --description="Posts about science and research" --allow-root
$WP wp term create category "Culture" --description="Posts about culture and society" --allow-root

echo "=== Creating tags ==="
$WP wp term create post_tag "docker" --allow-root
$WP wp term create post_tag "migration" --allow-root
$WP wp term create post_tag "cms" --allow-root
$WP wp term create post_tag "directus" --allow-root
$WP wp term create post_tag "tutorial" --allow-root

echo "=== Downloading sample images ==="
$WP wp media import "https://picsum.photos/800/600.jpg?random=1" \
  --title="Technology Banner" \
  --allow-root || echo "Image 1 import attempted"

$WP wp media import "https://picsum.photos/800/600.jpg?random=2" \
  --title="Science Banner" \
  --allow-root || echo "Image 2 import attempted"

$WP wp media import "https://picsum.photos/800/600.jpg?random=3" \
  --title="Culture Banner" \
  --allow-root || echo "Image 3 import attempted"

echo "=== Creating posts ==="

# Post 1: Published, Technology, multiple tags, featured image, custom fields
POST1=$($WP wp post create \
  --post_title="Getting Started with Docker Containers" \
  --post_content="<h2>Introduction to Docker</h2><p>Docker is a platform for developing, shipping, and running applications in containers. Containers allow a developer to package up an application with all of the parts it needs.</p><p>In this guide, we'll walk through the basics of containerization and how it can improve your development workflow.</p><h3>Why Docker?</h3><p>Docker provides consistency across environments, faster deployment cycles, and better resource utilization compared to traditional virtual machines.</p><!-- more --><h3>Getting Started</h3><p>First, install Docker Desktop on your machine. Then, create a Dockerfile that describes your application environment.</p><pre><code>FROM node:18-alpine\nWORKDIR /app\nCOPY . .\nRUN npm install\nCMD [\"npm\", \"start\"]</code></pre><p>This simple Dockerfile creates a Node.js application container.</p>" \
  --post_status=publish \
  --post_author=1 \
  --post_category="Technology" \
  --tags_input="docker,migration,tutorial" \
  --porcelain \
  --allow-root)

echo "Created post 1: $POST1"

# Post 2: Published, Science, fewer tags
POST2=$($WP wp post create \
  --post_title="The Future of Quantum Computing" \
  --post_content="<h2>Quantum Computing Revolution</h2><p>Quantum computing represents a fundamental shift in how we process information. Unlike classical computers that use bits, quantum computers use qubits that can exist in multiple states simultaneously.</p><p>Recent breakthroughs have brought us closer to practical quantum advantage in fields like cryptography, drug discovery, and optimization problems.</p><h3>Current State</h3><p>Companies like IBM, Google, and various startups are racing to build more stable and powerful quantum processors. The challenge remains in reducing error rates and increasing qubit count.</p><blockquote><p>\"Quantum computing will change the world. We just need to figure out how to make it work reliably.\" — Industry Expert</p></blockquote>" \
  --post_status=publish \
  --post_author=2 \
  --post_category="Science" \
  --tags_input="cms" \
  --porcelain \
  --allow-root)

echo "Created post 2: $POST2"

# Post 3: Draft, Technology, multiple tags
POST3=$($WP wp post create \
  --post_title="Migrating from WordPress to a Headless CMS" \
  --post_content="<h2>Why Go Headless?</h2><p>Traditional CMS platforms like WordPress couple the content management backend with the frontend presentation layer. A headless CMS separates these concerns, providing content via APIs.</p><p>This approach offers several advantages:</p><ul><li>Freedom to use any frontend framework</li><li>Better performance through static site generation</li><li>Improved security by reducing the attack surface</li><li>Multi-channel content delivery</li></ul><h3>Directus as a Headless CMS</h3><p>Directus wraps any SQL database with a dynamic API and provides an intuitive admin interface. It's open source and can be self-hosted.</p>" \
  --post_status=draft \
  --post_author=1 \
  --post_category="Technology" \
  --tags_input="directus,wordpress,migration" \
  --porcelain \
  --allow-root)

echo "Created post 3 (draft): $POST3"

# Post 4: Published, Culture, with image
POST4=$($WP wp post create \
  --post_title="Digital Art in the Modern Era" \
  --post_content="<h2>The Evolution of Digital Art</h2><p>Digital art has transformed from a niche curiosity into a mainstream creative medium. With tools becoming more accessible and powerful, artists are pushing the boundaries of what's possible.</p><p>From generative art to virtual reality installations, the digital medium offers unique possibilities that traditional media cannot match.</p><h3>Tools of the Trade</h3><p>Modern digital artists use a variety of tools including Procreate, Blender, TouchDesigner, and AI-assisted creation tools. The democratization of these tools has opened up creative expression to a wider audience.</p>" \
  --post_status=publish \
  --post_author=2 \
  --post_category="Culture" \
  --tags_input="tutorial" \
  --porcelain \
  --allow-root)

echo "Created post 4: $POST4"

# Post 5: Published, multiple categories, many tags, many custom fields
POST5=$($WP wp post create \
  --post_title="Building APIs with Modern Technologies" \
  --post_content="<h2>Modern API Development</h2><p>Building robust APIs is at the heart of modern software development. Whether you're creating a REST API, GraphQL endpoint, or real-time WebSocket service, the principles remain similar.</p><p>Good API design focuses on consistency, documentation, versioning, and security.</p><h3>REST vs GraphQL</h3><p>REST APIs use URLs and HTTP methods to model resources. GraphQL provides a single endpoint with a flexible query language. Each approach has trade-offs in terms of caching, complexity, and client flexibility.</p><h3>Authentication</h3><p>Token-based authentication (JWT, OAuth2) has become the standard for API security. Always use HTTPS, implement rate limiting, and validate all inputs.</p>" \
  --post_status=publish \
  --post_author=1 \
  --tags_input="docker,cms,directus,tutorial,migration" \
  --porcelain \
  --allow-root)

# Assign multiple categories to post 5
$WP wp post term set $POST5 category "Technology" "Science" --allow-root

echo "Created post 5: $POST5"

echo "=== Setting featured images ==="
# Get attachment IDs
ATTACHMENTS=$($WP wp post list --post_type=attachment --format=ids --allow-root)
echo "Available attachments: $ATTACHMENTS"

# Set featured images if attachments exist
ATTACH_ARRAY=($ATTACHMENTS)
if [ ${#ATTACH_ARRAY[@]} -ge 1 ]; then
  $WP wp post meta update $POST1 _thumbnail_id ${ATTACH_ARRAY[0]} --allow-root
  echo "Set featured image for post 1"
fi
if [ ${#ATTACH_ARRAY[@]} -ge 2 ]; then
  $WP wp post meta update $POST4 _thumbnail_id ${ATTACH_ARRAY[1]} --allow-root
  echo "Set featured image for post 4"
fi
if [ ${#ATTACH_ARRAY[@]} -ge 3 ]; then
  $WP wp post meta update $POST5 _thumbnail_id ${ATTACH_ARRAY[2]} --allow-root
  echo "Set featured image for post 5"
fi

echo "=== Adding custom fields ==="
# Post 1 custom fields
$WP wp post meta add $POST1 source_url "https://docs.docker.com/get-started/" --allow-root
$WP wp post meta add $POST1 reading_time "8" --allow-root
$WP wp post meta add $POST1 difficulty_level "beginner" --allow-root
$WP wp post meta add $POST1 is_featured "1" --allow-root

# Post 2 custom fields
$WP wp post meta add $POST2 source_url "https://quantum.ibm.com/" --allow-root
$WP wp post meta add $POST2 reading_time "12" --allow-root
$WP wp post meta add $POST2 difficulty_level "advanced" --allow-root
$WP wp post meta add $POST2 is_featured "0" --allow-root

# Post 3 custom fields
$WP wp post meta add $POST3 reading_time "6" --allow-root
$WP wp post meta add $POST3 difficulty_level "intermediate" --allow-root
$WP wp post meta add $POST3 is_featured "1" --allow-root

# Post 4 custom fields
$WP wp post meta add $POST4 source_url "https://en.wikipedia.org/wiki/Digital_art" --allow-root
$WP wp post meta add $POST4 reading_time "5" --allow-root
$WP wp post meta add $POST4 difficulty_level "beginner" --allow-root
$WP wp post meta add $POST4 is_featured "0" --allow-root

# Post 5 custom fields
$WP wp post meta add $POST5 source_url "https://developer.mozilla.org/en-US/docs/Web/HTTP" --allow-root
$WP wp post meta add $POST5 reading_time "10" --allow-root
$WP wp post meta add $POST5 difficulty_level "intermediate" --allow-root
$WP wp post meta add $POST5 is_featured "1" --allow-root

echo "=== Creating pages ==="
# About page (parent)
ABOUT=$($WP wp post create \
  --post_type=page \
  --post_title="About Us" \
  --post_content="<h2>About Migration Test Site</h2><p>This is a test site created to experiment with CMS content migration. We're exploring how content can be moved from WordPress to headless CMS platforms like Directus.</p><p>Our goal is to automate the migration process while preserving content structure, metadata, and relationships.</p>" \
  --post_status=publish \
  --menu_order=1 \
  --porcelain \
  --allow-root)

echo "Created About page: $ABOUT"

# Team page (child of About)
TEAM=$($WP wp post create \
  --post_type=page \
  --post_title="Our Team" \
  --post_content="<h2>Meet the Team</h2><p>Our team consists of experienced developers and content strategists working together on CMS migration solutions.</p><h3>Development Team</h3><ul><li><strong>Admin</strong> - Lead Developer</li><li><strong>Maria Rossi</strong> - Content Strategist</li></ul>" \
  --post_status=publish \
  --post_parent=$ABOUT \
  --menu_order=1 \
  --porcelain \
  --allow-root)

echo "Created Team page (child of About): $TEAM"

# Contact page (standalone)
CONTACT=$($WP wp post create \
  --post_type=page \
  --post_title="Contact" \
  --post_content="<h2>Get in Touch</h2><p>Have questions about CMS migration? Want to collaborate?</p><p>Email: <a href=\"mailto:contact@example.com\">contact@example.com</a></p><p>We'd love to hear from you!</p>" \
  --post_status=publish \
  --menu_order=2 \
  --porcelain \
  --allow-root)

echo "Created Contact page: $CONTACT"

echo "=== Registering custom post_type 'event' via must-use plugin ==="
docker compose exec -T wordpress bash -c "mkdir -p /var/www/html/wp-content/mu-plugins && cat > /var/www/html/wp-content/mu-plugins/event-type.php <<'PHPEOF'
<?php
add_action('init', function() {
    register_post_type('event', array(
        'public' => true,
        'label'  => 'Events',
        'supports' => array('title', 'editor', 'author', 'thumbnail'),
    ));
    register_taxonomy('event_cat', 'event', array(
        'public' => true,
        'label' => 'Event Categories',
        'hierarchical' => true,
    ));
});
PHPEOF"

echo "=== Creating 2 events ==="
EVENT1=$($WP wp post create \
  --post_type=event \
  --post_title='Directus Community Meetup' \
  --post_content='<p>Annual community meetup for Directus users and developers.</p>' \
  --post_status=publish \
  --post_author=1 \
  --porcelain \
  --allow-root)

EVENT2=$($WP wp post create \
  --post_type=event \
  --post_title='Headless CMS Conference 2026' \
  --post_content='<p>Multi-day conference covering headless CMS trends.</p>' \
  --post_status=publish \
  --post_author=2 \
  --porcelain \
  --allow-root)

$WP wp term create event_cat "Community" --allow-root || true
$WP wp term create event_cat "Conference" --allow-root || true
$WP wp post term add $EVENT1 event_cat "Community" --allow-root || true
$WP wp post term add $EVENT2 event_cat "Conference" --allow-root || true

echo "=== Simulating active plugin registrations ==="
$WP wp option update active_plugins '["hello-dolly/hello.php","my-tracker/main.php"]' --format=json --allow-root

echo ""
echo "=== Seeding Complete ==="
echo "Posts created: 5 (4 published, 1 draft)"
echo "Pages created: 3 (About, About/Team, Contact)"
echo "Categories: Technology, Science, Culture"
echo "Tags: docker, migration, cms, directus, tutorial"
echo "Custom fields: source_url, reading_time, difficulty_level, is_featured"
