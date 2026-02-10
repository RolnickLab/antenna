**Title**: Antenna: A Collaborative Platform for Automated Insect Monitoring

**Short Summary**: Open-source platform Antenna streamlines insect monitoring through automated AI identification, analysis, and collaborative data management tools.

**Abstract**:  
With the growth of camera traps for nocturnal insects, AI has been proposed as an effective way to parse large volumes of data. However, there remain challenges for non-AI experts in deploying computer vision algorithms and processing data at scale. Antenna is an open-source platform for insect monitoring that aims to bridge these gaps, allowing users to deploy AI models for insect detection and species identification and to manage their data to derive ecological insights. Antenna's user-centric approach minimizes technological barriers through an intuitive interface crafted for a wide-range of expertise and can efficiently handle large volumes of data from diverse sources and hardware to allow for insect monitoring across large spatial and temporal scales.

**Detailed Overview:**  
Antenna aims to bridge the gap between ecology and AI by fostering collaboration between entomologists, ecologists, machine-learning (ML) researchers and practitioners. Its vision encompasses four goals: 1\) establishing a collaborative hub where experts can interact and co-create solutions, 2\) enabling the development and deployment of ML models tailored to the specific needs of ecological research, 3\) building a global community dedicated to advancing insect monitoring using AI, and 4\) promoting open science to accelerate research and monitoring to greatly expedite conservation efforts. Antenna is built upon five core principles. (1) A user-centric approach to minimize technological barriers through an intuitive interface crafted for a wide-range of expertise. (2) A strong commitment to help ensure high data quality through an emphasises on data validation at each stage of the pipeline coupled with standard formats for better reliability, trustworthiness, and interoperability. (3) A dedication to openness and transparency through open-source code, data, and models, fostering reproducibility, and encouraging community-driven contributions. (4) Help to ensure interoperability by seamlessly integrating with existing ecological databases and tools for more efficient analyses and outcomes. (5) A platform that is capable of efficiently handling large volumes of data from diverse sources and machinery to allow for insect monitoring across large spatial and temporal scales.

**Presentation type:** Talk New tool or technology

**Which of the following subject areas best reflects your work?** Data and Informatics, Life Sciences (e.g. Ecology, Biology, Biodiversity, Conservation)

**Themes**: Technology-driven innovation ; Knowledge collaborations, Participatory science methods

---

**00:00 – Introduction & Team** Hello, my name is Michael Bunsen. I am a research software engineer. I work primarily with David Rolnick at MILA, the AI Research Institute based in Quebec and Montreal, and Maxim Larrivée at the Insectarium in Montreal. I also work with an amazing set of collaborators across the world who I am extremely grateful for.

Over the past few years, we have worked on a project—a platform and a set of software tools—that we are calling **Antenna**. We hope this platform will help you manage your insect monitoring efforts, whether that be for research or something else. Our goal is to help you scale up your projects and help you answer questions that you thought were previously impractical to answer, or even attempt to answer.

**01:10 – The Challenge: From Data to Insight** You may have noticed over the past few years that a lot of really cool cameras have been built for looking at moths at night or pollinators during the day. These range from DIY, open-source cameras to commercial cameras that you can buy off the shelf or special order.

But with more cameras and more AI models, that is simply more data. How do we turn that raw data into information and insights? How do we stay organized?. We can't be passing around CSV files for much longer, especially if we want to work together across borders, across disciplines, and across languages.

Think about the weather. This is a great example of a field that has already achieved this. We have devices that we trust, and we have algorithms we trust. Because of that, we can get weather predictions on our phones that we make decisions based on. Can we get there with biodiversity data? I hope so.

**02:30 – Antenna: The Orchestrator** To get there, it is going to take a team. It takes regional experts who know the local Lepidoptera taxonomy; it takes ML researchers who can fine-tune a model for you; and it takes policymakers or decision-makers who need information presented in a specific way.

We have built that idea of collaborative teamwork into Antenna. You can configure your team and give them different roles. Think of Antenna as an orchestrator between people, but also between technologies. You might have different cameras, different cloud storage, or different analysis approaches. Antenna acts as the intermediary to normalize your data coming in and out, standardize your taxonomy, and provide web access for anyone to collaborate, no matter what country they are in.

**03:45 – Case Study: Project Overview** Let’s look at a view of one specific project to see how this works. Tessa Reinhart, working in Pennsylvania, had a project over one summer using three cameras that she moved around.

She had 63 deployments, captured 500,000 images, and saw almost 700 unique species. That is a lot to manage, but she used Antenna as a content management system. Looking at her dashboard, we can already see some immediate insights. For example, at 2:00 a.m.—that was "party time". That was where the most moths showed up on average. We can also see that June was the most happening month for abundance.

**04:50 – The Workflow: Sessions and Occurrences** In the camera management view, you can see all your deployments and start to see where errors are—like whether a camera ran too long or a battery ran short and died early.

When you import images, they are automatically grouped into continuous monitoring sessions. For nocturnal insects, that means overnight, typically from Thursday evening to Friday morning. The pipeline works with any time-series data: you take pictures of multiple objects, run a detector, and then run a fine-grained classifier.

This leads you to the **Occurrence View**. This is where all your data comes together. You are building "occurrence records" with all the evidence you have collected. One occurrence should represent one individual moth. That might mean multiple frames of the same individual and the output of multiple algorithms. This is the dataset you are building, analyzing, and finally exporting.

**06:00 – Verification and Species Insights** Antenna provides tools for verifying these occurrences in batch, rejecting false positives, or rolling them up to coarser taxonomic levels if the AI isn't sure. You can view a summary of all unique species your project has seen, complete with reference images.

Let's look at a specific example: the Eastern Spruce Budworm. This is a native species, but it is of great interest to Natural Resources Canada because it can do a lot of damage in one season. Using the phenology flight chart generated by Antenna, you can see that this specific moth had two generations in one year—one in July and one in September.

If you find a really cool moth, you can click on the occurrence to see its specific details. You can see the identification history, showing which algorithms were run or which humans verified it. You can see exactly when it happened—for example, this one was at 2:09 a.m., right on schedule for the party. Uniquely, you can also see which other individuals it "co-occurred" with at the same time—essentially, you can see who its friends were.

**07:30 – Algorithms, Flexibility, and Export** Does this work for your data? If you are studying moths, our current algorithms might work just fine. But Antenna is a general processing framework. You can plug in your own algorithm, or you can use Antenna to collect raw data, verify it, and then export a dataset formatted specifically to train your own model in off-the-shelf frameworks like RoboFlow or HuggingFace.

We also have a post-processing framework where you can hook in statistical methods or general functions to help clean up noise, filter small images, and enhance the signal.

Finally, you need to get your data out. You can export programmatically or through the interface. You can export a Darwin Core file and import it directly to Gbif. We are already testing this in the field; we went to Panama this year for a really cool field test, and Natural Resources Canada is looking at putting these cameras at ports.

**09:00 – Conclusion: Uncertainty and Trust** To close, Antenna is intended to serve you. I really want to work together to measure uncertainty. We need to know where these tools are bad and where they are good so we can gain the confidence to scale them up. We want to reach a place where we have trust in the data.

Please tell us if this looks interesting, if we could take it in a different direction, or if you want to collaborate. Thank you so much for your time.

